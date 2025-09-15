import logging

from mcp.server.auth.settings import AuthSettings
from mcp.server.fastmcp.server import FastMCP

from settings import ResourceServerSettings
from token_verifier import IntrospectionTokenVerifier
from routes import tools, oauth

logger = logging.getLogger(__name__)


def create_resource_server(settings: ResourceServerSettings) -> FastMCP:
    """Create MCP Resource Server with Gravitee AM token introspection."""

    token_verifier = IntrospectionTokenVerifier(
        introspection_endpoint=settings.gravitee_am_introspection_endpoint,
        server_url=str(settings.server_url),
        validate_resource=settings.oauth_strict,
    )

    token_verifier.load_client_credentials()

    mcp = FastMCP(
        name="MCP Resource Server",
        instructions="Validates tokens via Gravitee AM introspection",
        host=settings.host,
        port=settings.port,
        debug=True,
        token_verifier=token_verifier,
        auth=AuthSettings(
            issuer_url=settings.gravitee_am_url,
            required_scopes=["openid", "full_profile"],
            resource_server_url=settings.server_url,
        ),
    )

    # Register routes in separate modules
    tools.register(mcp)
    oauth.register(mcp, settings, token_verifier)

    return mcp
