import logging
import click
from pydantic import AnyHttpUrl
from typing import Literal

from settings import ResourceServerSettings
from server import create_resource_server


@click.command()
@click.option("--port", default=8001, help="Port to listen on")
@click.option("--gravitee-am", default="http://localhost:8083", help="Gravitee AM URL")
@click.option(
    "--transport",
    default="streamable-http",
    type=click.Choice(["sse", "streamable-http"]),
    help="Transport protocol ('sse' or 'streamable-http')",
)
@click.option("--oauth-strict", is_flag=True, help="Enable RFC 8707 resource validation")
def main(port: int, gravitee_am: str, transport: Literal["sse", "streamable-http"], oauth_strict: bool):
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
            gravitee_am_userinfo_endpoint=f"{gravitee_am}/oidc/userinfo",
            oauth_strict=oauth_strict,
        )
    except ValueError as e:
        logging.error(f"Config error: {e}")
        return 1

    mcp_server = create_resource_server(settings)

    logging.info(f"🚀 MCP Resource Server running on {settings.server_url}")
    logging.info(f"🔑 Using Gravitee AM: {settings.gravitee_am_url}")

    mcp_server.run(transport=transport)


if __name__ == "__main__":
    main()
