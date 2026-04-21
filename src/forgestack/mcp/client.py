"""MCP client for interacting with MCP servers."""

import asyncio
import io
import logging
import os
import re
import sys
import warnings
from contextlib import AsyncExitStack, redirect_stderr
from pathlib import Path
from typing import Any

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from forgestack.config import ForgeStackConfig, MCPServerConfig
from forgestack.mcp.loader import MCPLoader

logger = logging.getLogger(__name__)

# Suppress async generator cleanup warnings from mcp/anyio library
# These occur during normal shutdown and are cosmetic, not functional issues
warnings.filterwarnings(
    "ignore",
    message=".*cancel scope.*",
    category=RuntimeWarning,
)
warnings.filterwarnings(
    "ignore",
    message=".*async_generator.*",
)

# Reduce noise from anyio during cleanup
logging.getLogger("anyio").setLevel(logging.WARNING)


def _suppress_async_cleanup_errors() -> None:
    """Suppress errors during async generator cleanup at shutdown.

    The MCP stdio_client async generator can produce errors when the event
    loop shuts down. These are cosmetic - the cleanup still succeeds.
    """
    # Store original hook
    original_hook = sys.unraisablehook

    def quiet_hook(unraisable: Any) -> None:
        # Suppress known MCP/anyio cleanup errors
        exc = unraisable.exc_value
        if exc is not None:
            error_str = str(exc)
            # Suppress cancel scope and async generator errors from MCP cleanup
            if any(pattern in error_str for pattern in [
                "cancel scope",
                "stdio_client",
                "different task",
            ]):
                return  # Silently ignore
        # Pass through other errors
        if original_hook is not None:
            original_hook(unraisable)

    sys.unraisablehook = quiet_hook

    # Also suppress the "an error occurred during closing" messages
    # These are printed directly to stderr by Python's async generator finalizer
    original_excepthook = sys.excepthook

    def quiet_excepthook(
        exc_type: type[BaseException],
        exc_value: BaseException,
        exc_tb: Any,
    ) -> None:
        # Suppress known MCP/anyio cleanup errors
        if exc_value is not None:
            error_str = str(exc_value)
            if any(pattern in error_str for pattern in [
                "cancel scope",
                "stdio_client",
                "different task",
            ]):
                return  # Silently ignore
        original_excepthook(exc_type, exc_value, exc_tb)

    sys.excepthook = quiet_excepthook


# Apply suppression at module load
_suppress_async_cleanup_errors()


class MCPServerConnection:
    """Represents an active connection to an MCP server."""

    def __init__(
        self,
        name: str,
        session: ClientSession,
        tools: list[dict[str, Any]],
    ) -> None:
        """Initialize server connection.

        Args:
            name: Server name
            session: MCP client session
            tools: List of tools provided by the server
        """
        self.name = name
        self.session = session
        self.tools = tools


class MCPClient:
    """Client for interacting with MCP servers.

    This client handles:
    - Loading MCP configuration from global config and per-repo configs
    - Connecting to MCP servers via stdio
    - Invoking MCP tools
    - Managing server lifecycles
    """

    def __init__(self, config: ForgeStackConfig) -> None:
        """Initialize the MCP client.

        Args:
            config: ForgeStack configuration
        """
        self.config = config
        self.loader = MCPLoader()
        self._connections: dict[str, MCPServerConnection] = {}
        self._available_tools: list[dict[str, Any]] = []
        self._exit_stack: AsyncExitStack | None = None

    def _resolve_env_var(self, value: str) -> str:
        """Resolve ${VAR} patterns in a string.

        Args:
            value: String potentially containing ${VAR} patterns

        Returns:
            String with environment variables resolved
        """
        pattern = r"\$\{([^}]+)\}"

        def replace(match: re.Match[str]) -> str:
            env_var = match.group(1)
            resolved = os.environ.get(env_var)
            if resolved is None:
                logger.warning(f"Environment variable '{env_var}' not found")
                return match.group(0)  # Keep original if not found
            return resolved

        return re.sub(pattern, replace, value)

    async def _connect_to_server(
        self,
        name: str,
        server_config: MCPServerConfig,
    ) -> MCPServerConnection | None:
        """Connect to a single MCP server.

        Args:
            name: Server name
            server_config: Server configuration

        Returns:
            MCPServerConnection or None if connection failed
        """
        try:
            # Resolve environment variables in env dict
            resolved_env = {}
            for key, value in server_config.env.items():
                resolved_env[key] = self._resolve_env_var(value)

            # Resolve environment variables in args
            resolved_args = [self._resolve_env_var(arg) for arg in server_config.args]

            # Create server parameters
            server_params = StdioServerParameters(
                command=server_config.command,
                args=resolved_args,
                env=resolved_env if resolved_env else None,
            )

            # Connect to the server
            if self._exit_stack is None:
                self._exit_stack = AsyncExitStack()
                await self._exit_stack.__aenter__()

            stdio_transport = await self._exit_stack.enter_async_context(
                stdio_client(server_params)
            )
            read_stream, write_stream = stdio_transport
            session = await self._exit_stack.enter_async_context(
                ClientSession(read_stream, write_stream)
            )

            # Initialize the session
            await session.initialize()

            # List available tools
            tools_result = await session.list_tools()
            tools = [
                {
                    "name": tool.name,
                    "description": tool.description or "",
                    "input_schema": tool.inputSchema if hasattr(tool, "inputSchema") else {},
                    "server": name,
                }
                for tool in tools_result.tools
            ]

            logger.info(f"Connected to MCP server '{name}' with {len(tools)} tools")
            return MCPServerConnection(name=name, session=session, tools=tools)

        except Exception as e:
            if server_config.optional:
                logger.debug(f"Optional MCP server '{name}' not available: {e}")
            else:
                logger.warning(f"Failed to connect to MCP server '{name}': {e}")
            return None

    async def _connect_global_servers(self) -> None:
        """Connect to all globally configured MCP servers."""
        for name, server_config in self.config.mcp.servers.items():
            connection = await self._connect_to_server(name, server_config)
            if connection:
                self._connections[name] = connection
                self._available_tools.extend(connection.tools)

    async def initialize_for_repo(self, repo_path: Path) -> list[dict[str, Any]]:
        """Initialize MCP servers for a repository.

        This connects to:
        1. Global servers defined in config.yaml
        2. Repo-specific servers from .mcp.json

        Args:
            repo_path: Path to the repository

        Returns:
            List of available tools from all MCP servers
        """
        # Connect to global servers if not already connected
        if not self._connections:
            await self._connect_global_servers()

        # Load repo-specific MCP configuration
        mcp_config = self.loader.load_config(repo_path)

        if mcp_config and "_error" not in mcp_config:
            # Get repo-specific server configurations
            servers = self.loader.get_servers(mcp_config)

            for server in servers:
                name = server.get("name", "")
                command = server.get("command")

                # Skip servers without a valid command (belt-and-suspenders check)
                if not name or not command or not isinstance(command, str):
                    logger.debug(f"Skipping server '{name}': no valid command")
                    continue

                if name not in self._connections:
                    # Create MCPServerConfig from repo config
                    server_config = MCPServerConfig(
                        command=command,
                        args=server.get("args", []),
                        env=server.get("env", {}),
                    )
                    connection = await self._connect_to_server(name, server_config)
                    if connection:
                        self._connections[name] = connection
                        self._available_tools.extend(connection.tools)

        # If no connections, return default tools
        if not self._connections:
            return self._get_default_tools()

        return self._available_tools

    def _get_default_tools(self) -> list[dict[str, Any]]:
        """Get default tools when no MCP servers are configured.

        Returns:
            List of default tool definitions
        """
        return [
            {
                "name": "file_read",
                "description": "Read contents of a file",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "path": {"type": "string", "description": "File path to read"},
                    },
                    "required": ["path"],
                },
            },
            {
                "name": "file_search",
                "description": "Search for files matching a pattern",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "pattern": {"type": "string", "description": "Glob pattern"},
                    },
                    "required": ["pattern"],
                },
            },
            {
                "name": "code_search",
                "description": "Search for code containing a term",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "query": {"type": "string", "description": "Search term"},
                    },
                    "required": ["query"],
                },
            },
        ]

    def _is_connection_error(self, error: Exception) -> bool:
        """Check if an error is a connection/SSE timeout error.

        Args:
            error: The exception to check

        Returns:
            True if this is a connection-related error
        """
        error_str = str(error).lower()
        connection_patterns = [
            "sse error",
            "timeout",
            "terminated",
            "connection",
            "closed",
            "eof",
            "broken pipe",
        ]
        return any(pattern in error_str for pattern in connection_patterns)

    def _remove_server(self, server_name: str) -> None:
        """Remove a disconnected server from the pool.

        Args:
            server_name: Name of the server to remove
        """
        if server_name in self._connections:
            del self._connections[server_name]
            # Remove tools from this server
            self._available_tools = [
                tool for tool in self._available_tools
                if tool.get("server") != server_name
            ]
            logger.info(f"Removed disconnected MCP server '{server_name}'")

    async def invoke_tool(
        self,
        tool_name: str,
        parameters: dict[str, Any],
    ) -> dict[str, Any]:
        """Invoke an MCP tool.

        Args:
            tool_name: Name of the tool to invoke
            parameters: Parameters to pass to the tool

        Returns:
            Tool result
        """
        # Find the server that provides this tool
        for connection in list(self._connections.values()):  # Copy to allow modification
            for tool in connection.tools:
                if tool["name"] == tool_name:
                    try:
                        result = await asyncio.wait_for(
                            connection.session.call_tool(
                                tool_name,
                                arguments=parameters,
                            ),
                            timeout=600.0,  # 10 minute timeout for tool calls
                        )
                        # Extract content from result
                        if hasattr(result, "content") and result.content:
                            content_items = []
                            for item in result.content:
                                if hasattr(item, "text"):
                                    content_items.append(item.text)
                            return {
                                "status": "success",
                                "content": "\n".join(content_items),
                            }
                        return {"status": "success", "result": str(result)}
                    except asyncio.TimeoutError:
                        logger.warning(
                            f"Tool '{tool_name}' timed out on server '{connection.name}'"
                        )
                        self._remove_server(connection.name)
                        return {
                            "status": "timeout",
                            "error": f"Tool '{tool_name}' timed out",
                        }
                    except Exception as e:
                        if self._is_connection_error(e):
                            logger.warning(
                                f"Connection error for '{tool_name}' on server "
                                f"'{connection.name}': {e}"
                            )
                            self._remove_server(connection.name)
                            return {
                                "status": "connection_error",
                                "error": f"Server '{connection.name}' disconnected",
                            }
                        logger.error(f"Error invoking tool '{tool_name}': {e}")
                        return {"status": "error", "error": str(e)}

        return {
            "status": "not_found",
            "error": f"Tool '{tool_name}' not found in any connected server",
        }

    async def shutdown(self) -> None:
        """Shutdown all active MCP server connections."""
        # Clear connections first to prevent use during shutdown
        self._connections.clear()
        self._available_tools.clear()

        if self._exit_stack:
            try:
                # Use wait_for with timeout to prevent hanging
                await asyncio.wait_for(self._exit_stack.aclose(), timeout=5.0)
            except asyncio.TimeoutError:
                logger.debug("MCP shutdown timed out, forcing cleanup")
            except RuntimeError as e:
                # Suppress cancel scope errors from async cleanup race conditions
                logger.debug(f"MCP shutdown cleanup (expected): {e}")
            except Exception as e:
                logger.warning(f"Error during MCP shutdown: {e}")
            finally:
                self._exit_stack = None

        logger.info("MCP client shutdown complete")

    def get_tools_description(self) -> str:
        """Get a description of available tools for prompts.

        Returns:
            Formatted string describing available tools
        """
        if not self._available_tools:
            return "No MCP tools available."

        lines = ["Available MCP Tools:"]
        for tool in self._available_tools:
            name = tool.get("name", "unknown")
            desc = tool.get("description", "No description")
            server = tool.get("server", "local")
            lines.append(f"  - {name} ({server}): {desc}")

        return "\n".join(lines)

    def get_connected_servers(self) -> list[str]:
        """Get list of connected server names.

        Returns:
            List of connected server names
        """
        return list(self._connections.keys())
