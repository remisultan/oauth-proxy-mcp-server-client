from typing import Any
from pydantic import AnyHttpUrl
from pydantic_settings import BaseSettings, SettingsConfigDict


class ResourceServerSettings(BaseSettings):
    """Settings for the MCP Resource Server using Gravitee AM."""

    model_config = SettingsConfigDict(env_prefix="MCP_RESOURCE_")

    host: str = "localhost"
    port: int = 8001
    server_url: AnyHttpUrl = AnyHttpUrl("http://localhost:8001")

    gravitee_am_url: AnyHttpUrl = AnyHttpUrl("http://localhost:8092")
    gravitee_am_introspection_endpoint: str = "http://localhost:8092/oauth/introspect"

    # OAuth2 / MCP
    mcp_scope: str = "username"
    oauth_strict: bool = False

    def __init__(self, **data: Any):
        super().__init__(**data)
