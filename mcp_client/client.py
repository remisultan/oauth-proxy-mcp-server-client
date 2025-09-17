import ssl
from typing import Any


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


import os
import aiohttp
from datetime import timedelta
from typing import Any

from mcp.client.session import ClientSession
from mcp.client.sse import sse_client
from mcp.client.streamable_http import streamablehttp_client
from auth import create_oauth_provider


class AgentClient:
    """MCP client that integrates with Azure OpenAI Agent via API key."""
    def __init__(self, server_url: str, transport_type: str = "streamable_http"):
        self.tools = []
        self.messages = [
            {"role": "system", "content": "You are an MCP-connected Azure agent."},
        ]
        self.server_url = server_url
        self.transport_type = transport_type
        self.session: ClientSession | None = None

        # MCP OAuth provider
        self.oauth_provider = create_oauth_provider(
            self.server_url, scopes=["openid", "full_profile"]
        )

        # Azure config from env vars
        self.azure_endpoint = os.getenv("AZURE_OPENAI_ENDPOINT", "").rstrip("/")
        self.azure_deployment = os.getenv("AZURE_OPENAI_DEPLOYMENT", "")
        self.azure_api_key = os.getenv("AZURE_OPENAI_API_KEY", "")

        if not (self.azure_endpoint and self.azure_deployment and self.azure_api_key):
            raise RuntimeError(
                "Missing Azure config. Please set AZURE_OPENAI_ENDPOINT, "
                "AZURE_OPENAI_DEPLOYMENT, and AZURE_OPENAI_API_KEY"
            )

    async def connect(self):
        print(f"🔗 Connecting to {self.server_url} with {self.transport_type}...")

        if self.transport_type == "sse":
            async with sse_client(self.server_url, auth=self.oauth_provider) as (r, w):
                await self._run_session(r, w, None)
        else:
            async with streamablehttp_client(
                self.server_url, auth=self.oauth_provider, timeout=timedelta(seconds=60)
            ) as (r, w, get_session_id):
                await self._run_session(r, w, get_session_id)

    async def _run_session(self, read_stream, write_stream, get_session_id):
        async with ClientSession(read_stream, write_stream) as session:
            self.session = session
            await session.initialize()
            print("✅ MCP Session initialized")

            if get_session_id:
                sid = get_session_id()
                if sid:
                    print(f"Session ID: {sid}")

            await self.interactive_loop()

    async def query_agent(self, prompt: str, role:str = "user", includeTools: bool = False) -> Any:
        """Send prompt to Azure OpenAI agent with API key."""

        url = (
            f"{self.azure_endpoint}/openai/deployments/"
            f"{self.azure_deployment}/chat/completions?api-version=2024-05-01-preview"
        )

        headers = {
            "api-key": self.azure_api_key,
            "Content-Type": "application/json",
        }

        self.messages.append(
            {"role": role, "content": prompt}
        )

        body = {
            "messages": self.messages,
            "stream": False,
        }

        # Optionally expose MCP tools
        tool_list = []
        if includeTools:
            for tool in self.tools:
                tool_list.append({
                    "type": "function",
                    "function": {
                        "name": tool.name,
                        "description": tool.description or "",
                        "parameters": tool.inputSchema or {},
                    }
                })

        if tool_list:
            body["tools"] = tool_list

        ssl_context = ssl.create_default_context()
        ssl_context.check_hostname = False
        ssl_context.verify_mode = ssl.CERT_NONE

        async with aiohttp.ClientSession() as client:
            async with client.post(url, headers=headers, json=body, ssl=ssl_context) as resp:
                if resp.status != 200:
                    raise RuntimeError(f"Agent call failed: {resp.status} {await resp.text()}")
                data = await resp.json()
                message = data["choices"][0]["message"]
                content = message["content"]

                if content:
                    self.messages.append(
                        {"role": "assistant", "content": content},
                    )
                    return content

                tool_calls = message["tool_calls"]

                if tool_calls:
                    for function in tool_calls:
                        self.tools = [tool for tool in self.tools if tool.name != function["function"]["name"]]
                        await self.query_agent(
                            await self.call_tool(function["function"]["name"], eval(function["function"]["arguments"])),
                            includeTools= len(self.tools) > 0
                        )

                return await self.query_agent("Give the answer", includeTools=False)


    async def interactive_loop(self):
        print("\n🤖 Agent Client (commands: ask <prompt>, quit)")
        while True:
            cmd = input("agent> ").strip()
            if cmd == "quit":
                break
            elif cmd.startswith("ask "):
                prompt = cmd[4:]
                try:
                    result = await self.session.list_tools()
                    self.tools = result.tools
                    self.messages =  [
                        {"role": "system", "content": "You are an MCP-connected Azure agent."},
                    ]
                    reply = await self.query_agent(prompt, includeTools=True)
                    print(f"\n💬 Agent reply:\n{reply}\n")
                except Exception as e:
                    print(f"❌ Agent error: {e}")
            else:
                print("❌ Unknown command")

    async def call_tool(self, tool_name: str, args: dict[str, Any] | None = None) -> str:
        if not self.session:
            print("❌ Not connected")
            return
        result = await self.session.call_tool(tool_name, args or {})
        response = f"{tool_name}:\n"
        response += f"<tool_response>\n"
        for c in getattr(result, "content", []):
            response += c.text if c.type == "text" else str(c)
        return response + "</tool_response>"
