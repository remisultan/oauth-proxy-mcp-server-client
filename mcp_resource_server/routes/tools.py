import datetime
from typing import Any

from mcp.server.fastmcp import Context
from mcp.server.fastmcp.exceptions import ToolError

def register(mcp):

    def get_user_claims(ctx:Context):
        return ctx.request_context.request.user.access_token.claims

    @mcp.tool()
    async def get_time(ctx:Context) -> dict[str, Any]:
        """Return current server time (protected by OAuth)."""
        now = datetime.datetime.now()
        return {
            "current_time": now.isoformat(),
            "timezone": "UTC",
            "timestamp": now.timestamp(),
            "formatted": now.strftime("%Y-%m-%d %H:%M:%S"),
        }

    @mcp.tool()
    async def get_time_but_you_are_an_admin(ctx:Context) -> dict[str, Any]:
        """
        Return current server time (protected by OAuth).
        """
        claims = get_user_claims(ctx)
        if "graviteesource.com" in claims['email']:
            now = datetime.datetime.now()
            return {
                "current_time": now.isoformat(),
                "timezone": "UTC",
                "timestamp": now.timestamp(),
                "formatted": now.strftime("%Y-%m-%d %H:%M:%S"),
            }
        else:
            raise ToolError("403", "Forbidden", "Cannot get time sorry!")

    @mcp.tool()
    async def get_user_profile(ctx: Context) -> dict[str, Any]:
        """Return current server time (protected by OAuth)."""
        return get_user_claims(ctx)