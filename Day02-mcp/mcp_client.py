"""
MCP Client Manager — Dynamic Client Adapter for Model Context Protocol Servers.

Features:
    - Reads declarative `mcp_servers.json` configuration (or defaults to local k8s_server).
    - Spawns and manages external tool servers as isolated child processes via stdio.
    - Uses AsyncExitStack for clean process lifecycle management and automatic teardown.
    - Translates MCP tool schemas into OpenAI-compatible function calling schemas.
    - Fault-tolerant execution: catches crashes/timeouts without terminating the agent.
"""

from contextlib import AsyncExitStack
import json
import os
from pathlib import Path
import shutil
import sys
from typing import Any, Dict, List, Tuple
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

# Base directory for relative path resolution
BASE_DIR = Path(__file__).resolve().parent


class MCPClientManager:
    """Manages connections to one or more Model Context Protocol (MCP) servers."""

    def __init__(self, config_path: Path | str | None = None):
        self.config_path = Path(config_path) if config_path else BASE_DIR / "mcp_servers.json"
        self._exit_stack: AsyncExitStack | None = None
        self._sessions: Dict[str, ClientSession] = {}
        self._tool_to_session: Dict[str, Tuple[str, ClientSession]] = {}
        self._schemas: List[Dict[str, Any]] = []

    async def __aenter__(self):
        await self.start()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.stop()

    def load_server_configs(self) -> Dict[str, Dict[str, Any]]:
        """Load server definitions from config file or return default k8s_server config."""
        if self.config_path.exists():
            try:
                with open(self.config_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    servers = data.get("mcpServers", {})
                    if servers:
                        return servers
            except Exception as e:
                print(f"\033[93m[MCP Warning] Failed to parse {self.config_path}: {e}\033[0m")

        # Fallback default configuration if mcp_servers.json is absent or empty
        return {
            "kubernetes": {
                "command": "python",
                "args": [str(BASE_DIR / "k8s_server.py")],
                "description": "Default Kubernetes FastMCP Server",
            }
        }

    async def start(self):
        """Spawn all configured MCP servers and discover their available tools."""
        self._exit_stack = AsyncExitStack()
        configs = self.load_server_configs()

        print("\n\033[94m🔌 Initializing Model Context Protocol (MCP) Client...\033[0m")

        for server_name, cfg in configs.items():
            raw_cmd = cfg.get("command", "python")
            raw_args = cfg.get("args", [])
            env = cfg.get("env", None)

            # Resolve python command to current virtual environment python
            if raw_cmd in ("python", "python3"):
                cmd = sys.executable
            else:
                cmd = shutil.which(raw_cmd) or raw_cmd

            # Resolve relative arguments (e.g. "k8s_server.py" -> full path)
            resolved_args = []
            for arg in raw_args:
                if (BASE_DIR / arg).exists():
                    resolved_args.append(str(BASE_DIR / arg))
                else:
                    resolved_args.append(arg)

            try:
                params = StdioServerParameters(command=cmd, args=resolved_args, env=env)
                read_stream, write_stream = await self._exit_stack.enter_async_context(
                    stdio_client(params)
                )
                session = await self._exit_stack.enter_async_context(
                    ClientSession(read_stream, write_stream)
                )
                await session.initialize()

                # Discover tools exposed by this server
                tools_response = await session.list_tools()
                server_tool_count = 0

                for mcp_tool in tools_response.tools:
                    tool_name = mcp_tool.name
                    # Convert to OpenAI-compatible function schema
                    parameters = (
                        mcp_tool.inputSchema
                        if hasattr(mcp_tool, "inputSchema") and isinstance(mcp_tool.inputSchema, dict)
                        else {"type": "object", "properties": {}}
                    )

                    schema = {
                        "type": "function",
                        "function": {
                            "name": tool_name,
                            "description": mcp_tool.description or f"Tool provided by MCP server '{server_name}'",
                            "parameters": parameters,
                        },
                    }
                    self._schemas.append(schema)
                    self._tool_to_session[tool_name] = (server_name, session)
                    server_tool_count += 1

                self._sessions[server_name] = session
                print(
                    f"\033[92m  ✓ Connected to '{server_name}' over stdio ({server_tool_count} tool(s) registered)\033[0m"
                )

            except Exception as e:
                print(f"\033[91m  ✗ Failed to start MCP server '{server_name}': {e}\033[0m")

        print(f"\033[94m🔌 Total MCP tools ready for LLM: {len(self._schemas)}\033[0m\n")

    async def stop(self):
        """Cleanly terminate all MCP server subprocesses."""
        if self._exit_stack:
            await self._exit_stack.aclose()
            self._exit_stack = None
            self._sessions.clear()
            self._tool_to_session.clear()
            self._schemas.clear()

    @property
    def schemas(self) -> List[Dict[str, Any]]:
        """Return all OpenAI-compatible tool schemas for LLM dispatch."""
        return self._schemas

    @property
    def tool_names(self) -> List[str]:
        """Return names of all discovered tools."""
        return sorted(self._tool_to_session.keys())

    async def execute(self, tool_name: str, arguments: Dict[str, Any] | str = None) -> str:
        """
        Execute a tool on its parent MCP server over JSON-RPC.

        Args:
            tool_name: Name of the registered MCP tool.
            arguments: Tool arguments as a dictionary or JSON string.

        Returns:
            str: Output from the MCP server, or a clean JSON error on failure.
        """
        if tool_name not in self._tool_to_session:
            return json.dumps({"error": f"Tool '{tool_name}' not found on any active MCP server."})

        server_name, session = self._tool_to_session[tool_name]

        # Parse string arguments if needed
        if isinstance(arguments, str):
            try:
                arguments = json.loads(arguments) if arguments.strip() else {}
            except Exception as e:
                return json.dumps({"error": f"Invalid JSON arguments: {e}"})
        elif arguments is None:
            arguments = {}

        try:
            # Call tool over stdio JSON-RPC
            result = await session.call_tool(tool_name, arguments=arguments)

            # Extract text blocks from response
            text_blocks = [
                content.text
                for content in result.content
                if hasattr(content, "text") and content.text
            ]

            if not text_blocks:
                return f"[MCP server '{server_name}'] Tool completed with no text output."

            return "\n".join(text_blocks)

        except Exception as e:
            # Fault isolation: tool error does not crash the agent
            return json.dumps({
                "mcp_error": f"Execution failed on server '{server_name}'",
                "details": str(e)
            })
