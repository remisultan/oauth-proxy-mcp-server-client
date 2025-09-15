import datetime
from typing import Any


def register(mcp):
    @mcp.tool()
    async def get_time() -> dict[str, Any]:
        """Return current server time (protected by OAuth)."""
        now = datetime.datetime.now()
        return {
            "current_time": now.isoformat(),
            "timezone": "UTC",
            "timestamp": now.timestamp(),
            "formatted": now.strftime("%Y-%m-%d %H:%M:%S"),
        }

    @mcp.tool()
    async def get_time_but_you_are_an_admin() -> dict[str, Any]:
        """
        Return current server time (protected by OAuth).

        """
        now = datetime.datetime.now()
        return {
            "current_time": now.isoformat(),
            "timezone": "UTC",
            "timestamp": now.timestamp(),
            "formatted": now.strftime("%Y-%m-%d %H:%M:%S"),
        }