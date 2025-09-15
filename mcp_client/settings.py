import os

class ClientSettings:
    """Settings for the MCP Auth Client."""

    def __init__(self):
        self.port = int(os.getenv("MCP_SERVER_PORT", 8001))
        self.transport_type = os.getenv("MCP_TRANSPORT_TYPE", "streamable_http")

    @property
    def server_url(self) -> str:
        if self.transport_type == "streamable_http":
            return f"http://localhost:{self.port}/mcp"
        return f"http://localhost:{self.port}/sse"