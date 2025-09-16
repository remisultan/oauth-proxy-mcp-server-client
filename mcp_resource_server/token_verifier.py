"""Example token verifier implementation using OAuth 2.0 Token Introspection (RFC 7662)."""
import json
import logging
from pathlib import Path
from typing import Any

from mcp.server.auth.provider import AccessToken, TokenVerifier
from mcp.shared.auth_utils import check_resource_allowed, resource_url_from_server_url

logger = logging.getLogger(__name__)
DEFAULT_CREDENTIALS_PATH = Path.home() / ".mcp_server" / "client_credentials.json"

class AccessTokenWithClaims(AccessToken):
    claims: dict

class IntrospectionTokenVerifier(TokenVerifier):
    """Example token verifier that uses OAuth 2.0 Token Introspection (RFC 7662).

    This is a simple example implementation for demonstration purposes.
    Production implementations should consider:
    - Connection pooling and reuse
    - More sophisticated error handling
    - Rate limiting and retry logic
    - Comprehensive configuration options
    """

    def __init__(
        self,
        introspection_endpoint: str,
        userinfo_endpoint: str,
        server_url: str,
        validate_resource: bool = False,
    ):
        self.introspection_endpoint = introspection_endpoint
        self.userinfo_endpoint = userinfo_endpoint
        self.server_url = server_url
        self.validate_resource = validate_resource
        self.resource_url = resource_url_from_server_url(server_url)
        # Default client creds (will be updated by /register)
        self.client_id: str | None = None
        self.client_secret: str | None = None

    def set_client_credentials(
        self, client_id: str, client_secret: str
    ):
        """Update the client credentials (optionally persisting them to disk)."""
        self.client_id = client_id
        self.client_secret = client_secret

    def load_client_credentials(self, file_path: Path = DEFAULT_CREDENTIALS_PATH):
        """Load client_id and client_secret from a JSON file."""
        if file_path.exists():
            logger.info(f"Loading credentials from {file_path}")
            with file_path.open("r") as f:
                creds = json.load(f)

            self.set_client_credentials(
                creds.get("client_id"),
                creds.get("client_secret")
            )

    async def verify_token(self, token: str) -> AccessTokenWithClaims | None:
        """Verify token via introspection endpoint."""
        import httpx

        """Verify token with currently stored client credentials."""
        if not self.client_id or not self.client_secret:
            raise ValueError("No client credentials set for introspection")

        # Validate URL to prevent SSRF attacks
        if not self.introspection_endpoint.startswith(("https://", "http://localhost", "http://127.0.0.1")):
            logger.warning(f"Rejecting introspection endpoint with unsafe scheme: {self.introspection_endpoint}")
            return None

        # Configure secure HTTP client
        timeout = httpx.Timeout(10.0, connect=5.0)
        limits = httpx.Limits(max_connections=10, max_keepalive_connections=5)

        async with httpx.AsyncClient(
            timeout=timeout,
            limits=limits,
            verify=True,  # Enforce SSL verification
        ) as client:
            try:
                response = await client.post(
                    self.introspection_endpoint,
                    data={"token": token, "client_id": self.client_id, "client_secret": self.client_secret},
                    headers=[("Content-Type", "application/x-www-form-urlencoded")],
                )

                if response.status_code != 200:
                    logger.debug(f"Token introspection returned status {response.status_code}")
                    return None

                data = response.json()
                if not data.get("active", False):
                    return None

                # RFC 8707 resource validation (only when --oauth-strict is set)
                if self.validate_resource and not self._validate_resource(data):
                    logger.warning(f"Token resource validation failed. Expected: {self.resource_url}")
                    return None

                userInfo = await client.get(
                    self.userinfo_endpoint,
                    headers=[("Authorization", f"Bearer {token}")],
                )

                return AccessTokenWithClaims(
                    token=token,
                    client_id=data.get("client_id", self.client_id),
                    scopes=data.get("scope").split(" "),
                    expires_at=data.get("exp"),
                    resource=data.get("aud"),
                    claims=userInfo.json()
                )
            except Exception as e:
                logger.warning(f"Token introspection failed: {e}")
                return None

    def _validate_resource(self, token_data: dict[str, Any]) -> bool:
        """Validate token was issued for this resource mcp_resource_server."""
        if not self.server_url or not self.resource_url:
            return False  # Fail if strict validation requested but URLs missing

        # Check 'aud' claim first (standard JWT audience)
        aud: list[str] | str | None = token_data.get("aud")
        if isinstance(aud, list):
            for audience in aud:
                if self._is_valid_resource(audience):
                    return True
            return False
        elif aud:
            return self._is_valid_resource(aud)

        # No resource binding - invalid per RFC 8707
        return False

    def _is_valid_resource(self, resource: str) -> bool:
        """Check if resource matches this mcp_resource_server using hierarchical matching."""
        if not self.resource_url:
            return False

        return check_resource_allowed(requested_resource=self.resource_url, configured_resource=resource)

