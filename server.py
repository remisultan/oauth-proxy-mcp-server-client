"""
MCP Resource Server with Gravitee AM Token Introspection.

This server validates tokens via Gravitee AM introspection and serves MCP resources.
Demonstrates RFC 9728 Protected Resource Metadata for AS/RS separation.

NOTE: this is a simplified example for demonstration purposes.
This is not a production-ready implementation.
"""

import datetime
import logging
from typing import Any, Literal

import click
from pydantic import AnyHttpUrl
from pydantic_settings import BaseSettings, SettingsConfigDict

from mcp.server.auth.settings import AuthSettings
from mcp.server.fastmcp.server import FastMCP

from token_verifier import IntrospectionTokenVerifier

logger = logging.getLogger(__name__)


class ResourceServerSettings(BaseSettings):
    """Settings for the MCP Resource Server using Gravitee AM."""

    model_config = SettingsConfigDict(env_prefix="MCP_RESOURCE_")

    # Server settings
    host: str = "localhost"
    port: int = 8001
    server_url: AnyHttpUrl = AnyHttpUrl("http://localhost:8001")

    # Gravitee AM settings
    gravitee_am_url: AnyHttpUrl = AnyHttpUrl("https://am.gateway.master.gravitee.dev/ai-ml")
    gravitee_am_introspection_endpoint: str = "https://am.gateway.master.gravitee.dev/ai-ml/oauth/introspect"

    # MCP settings
    mcp_scope: str = "username"

    # RFC 8707 resource validation
    oauth_strict: bool = False

    def __init__(self, **data: Any):
        """Initialize settings with values from environment variables."""
        super().__init__(**data)


def create_resource_server(settings: ResourceServerSettings) -> FastMCP:
    """
    Create MCP Resource Server with Gravitee AM token introspection.

    This server:
    1. Provides protected resource metadata (RFC 9728)
    2. Validates tokens via Gravitee AM introspection
    3. Serves MCP tools and resources
    """
    # Create token verifier for introspection with RFC 8707 resource validation
    token_verifier = IntrospectionTokenVerifier(
        introspection_endpoint=settings.gravitee_am_introspection_endpoint,
        server_url=str(settings.server_url),
        validate_resource=settings.oauth_strict,
    )

    # Create FastMCP server as a Resource Server
    mcp = FastMCP(
        name="MCP Resource Server",
        instructions="Resource Server that validates tokens via Gravitee AM introspection",
        host=settings.host,
        port=settings.port,
        debug=True,
        token_verifier=token_verifier,
        auth=AuthSettings(
            issuer_url=settings.gravitee_am_url,
            required_scopes=[],
            resource_server_url=settings.server_url,
        ),
    )

    @mcp.tool()
    async def get_time() -> dict[str, Any]:
        """
        Get the current server time.

        This tool demonstrates that system information can be protected
        by OAuth authentication. User must be authenticated to access it.
        """
        now = datetime.datetime.now()
        return {
            "current_time": now.isoformat(),
            "timezone": "UTC",
            "timestamp": now.timestamp(),
            "formatted": now.strftime("%Y-%m-%d %H:%M:%S"),
        }

    @mcp.custom_route("/register", methods=["POST"])
    async def register_client(request):
        """
        Dynamic Client Registration (RFC 7591)
        Forward the registration request to Gravitee AM and return client_id/secret
        """
        try:
            client_metadata = await request.json()
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{settings.gravitee_am_url}/oidc/register",
                    json=client_metadata,
                    headers={"Content-Type": "application/json"},
                    timeout=10,
                )
                response.raise_for_status()
                data = response.json()

                # Store the credentials inside the verifier
                token_verifier.set_client_credentials(
                    client_id=data["client_id"],
                    client_secret=data["client_secret"],
                )
            return JSONResponse(content=data)
        except Exception as e:
            return {"error": str(e)}, 400

    from urllib.parse import urlencode
    from starlette.responses import RedirectResponse

    @mcp.custom_route("/authorize", methods=["GET"])
    async def authorize(request):
        """
        Redirect the client to Gravitee AM authorization endpoint
        """
        # Extract query params from client request
        params = dict(request.query_params)

        # Build Gravitee AM authorize URL
        authorize_url = f"{settings.gravitee_am_url}/oauth/authorize?{urlencode(params)}"

        # Redirect browser
        return RedirectResponse(authorize_url)

    import httpx
    from starlette.responses import JSONResponse
    from starlette.status import HTTP_400_BAD_REQUEST

    @mcp.custom_route("/token", methods=["POST"])
    async def token_proxy(request):
        """
        Proxy token exchange to Gravitee AM.
        Forward the raw body and headers as-is.
        """
        try:
            body = await request.body()  # raw x-www-form-urlencoded data

            async with httpx.AsyncClient() as client:
                resp = await client.post(
                    f"{settings.gravitee_am_url}/oauth/token",
                    content=body,
                    headers=[("Content-Type", "application/x-www-form-urlencoded")],
                    timeout=10,
                )
                resp.raise_for_status()
                data = resp.json()

            return JSONResponse(content=data)

        except httpx.HTTPStatusError as e:
            return JSONResponse(
                {"error": f"HTTP error: {e.response.status_code}", "details": e.response.text},
                status_code=e.response.status_code,
            )
        except Exception as e:
            return JSONResponse({"error": str(e)}, status_code=HTTP_400_BAD_REQUEST)

    return mcp


@click.command()
@click.option("--port", default=8001, help="Port to listen on")
@click.option("--gravitee-am", default="http://localhost:8083", help="Gravitee AM URL")
@click.option(
    "--transport",
    default="streamable-http",
    type=click.Choice(["sse", "streamable-http"]),
    help="Transport protocol to use ('sse' or 'streamable-http')",
)
@click.option(
    "--oauth-strict",
    is_flag=True,
    help="Enable RFC 8707 resource validation",
)
def main(port: int, gravitee_am: str, transport: Literal["sse", "streamable-http"], oauth_strict: bool) -> int:
    """Run MCP Resource Server with Gravitee AM as OAuth2 provider."""
    logging.basicConfig(level=logging.INFO)

    try:
        am_url = AnyHttpUrl(gravitee_am)
        settings = ResourceServerSettings(
            host="localhost",
            port=port,
            server_url=AnyHttpUrl(f"http://localhost:{port}"),
            gravitee_am_url=am_url,
            gravitee_am_introspection_endpoint=f"{gravitee_am}/oauth/introspect",
            oauth_strict=oauth_strict,
        )
    except ValueError as e:
        logger.error(f"Configuration error: {e}")
        logger.error("Make sure to provide a valid Gravitee AM URL")
        return 1

    try:
        mcp_server = create_resource_server(settings)

        logger.info(f"🚀 MCP Resource Server running on {settings.server_url}")
        logger.info(f"🔑 Using Gravitee AM: {settings.gravitee_am_url}")

        # Run the server - this blocks and keeps running
        mcp_server.run(transport=transport)
        return 0
    except Exception:
        logger.exception("Server error")
        return 1


# Inside create_resource_server(settings)

if __name__ == "__main__":
    main()  # type: ignore[call-arg]
