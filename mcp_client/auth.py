import webbrowser
from mcp.client.auth import OAuthClientProvider
from mcp.shared.auth import OAuthClientMetadata
from storage import InMemoryTokenStorage
from callback import CallbackServer


def create_oauth_provider(server_url: str) -> OAuthClientProvider:
    """Factory for OAuthClientProvider with default redirect/callback handling."""
    callback_server = CallbackServer(port=3030)
    callback_server.start()

    async def callback_handler():
        code = callback_server.wait_for_callback()
        state = callback_server.get_state()
        callback_server.stop()
        return code, state

    async def redirect_handler(authorization_url: str):
        print(f"🌐 Opening browser for authorization: {authorization_url}")
        webbrowser.open(authorization_url)

    client_metadata = OAuthClientMetadata.model_validate(
        {
            "client_name": "Simple Auth Client",
            "redirect_uris": ["http://localhost:3030/callback"],
            "grant_types": ["authorization_code", "refresh_token"],
            "response_types": ["code"],
            "token_endpoint_auth_method": "client_secret_post",
        }
    )

    return OAuthClientProvider(
        server_url=server_url.replace("/mcp", ""),
        client_metadata=client_metadata,
        storage=InMemoryTokenStorage(),
        redirect_handler=redirect_handler,
        callback_handler=callback_handler,
    )
