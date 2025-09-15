from datetime import timedelta
from typing import Any
from mcp.client.session import ClientSession
from mcp.client.sse import sse_client
from mcp.client.streamable_http import streamablehttp_client
from auth import create_oauth_provider


class SimpleAuthClient:
    """MCP client with OAuth authentication."""

    def __init__(self, server_url: str, transport_type: str = "streamable_http"):
        self.server_url = server_url
        self.transport_type = transport_type
        self.session: ClientSession | None = None

    async def connect(self):
        print(f"🔗 Connecting to {self.server_url} with {self.transport_type}...")

        oauth_provider = create_oauth_provider(self.server_url, scopes=["openid", "full_profile"])

        if self.transport_type == "sse":
            async with sse_client(self.server_url, auth=oauth_provider) as (r, w):
                await self._run_session(r, w, None)
        else:
            async with streamablehttp_client(
                self.server_url, auth=oauth_provider, timeout=timedelta(seconds=60)
            ) as (r, w, get_session_id):
                await self._run_session(r, w, get_session_id)

    async def _run_session(self, read_stream, write_stream, get_session_id):
        async with ClientSession(read_stream, write_stream) as session:
            self.session = session
            await session.initialize()
            print("✅ Session initialized")

            if get_session_id:
                sid = get_session_id()
                if sid:
                    print(f"Session ID: {sid}")

            await self.interactive_loop()

    async def list_tools(self):
        if not self.session:
            print("❌ Not connected")
            return
        result = await self.session.list_tools()
        if result.tools:
            print("\n📋 Available tools:")
            for tool in result.tools:
                print(f"- {tool.name}: {tool.description or ''}")
        else:
            print("No tools available")

    async def call_tool(self, tool_name: str, args: dict[str, Any] | None = None):
        if not self.session:
            print("❌ Not connected")
            return
        result = await self.session.call_tool(tool_name, args or {})
        print(f"\n🔧 Tool '{tool_name}' result:")
        for c in getattr(result, "content", []):
            print(c.text if c.type == "text" else c)

    async def interactive_loop(self):
        print("\n🎯 Interactive Client (commands: list, call <tool> [json], quit)")
        while True:
            cmd = input("mcp> ").strip()
            if cmd == "quit":
                break
            if cmd == "list":
                await self.list_tools()
            elif cmd.startswith("call "):
                import json
                _, tool, *rest = cmd.split(maxsplit=2)
                args = {}
                if rest:
                    try:
                        args = json.loads(rest[0])
                    except Exception:
                        print("❌ Invalid JSON args")
                await self.call_tool(tool, args)
            else:
                print("❌ Unknown command")
