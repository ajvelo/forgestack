"""MCP tool router for routing tool calls to appropriate servers."""

from collections.abc import Callable
from typing import Any


class MCPRouter:
    """Routes MCP tool calls to appropriate handlers.

    The router maintains a registry of tool handlers and routes
    incoming tool calls to the appropriate handler based on
    tool name or server association.
    """

    def __init__(self) -> None:
        """Initialize the MCP router."""
        self._handlers: dict[str, Callable] = {}
        self._server_handlers: dict[str, Callable] = {}
        self._fallback_handler: Callable | None = None

    def register_tool(
        self,
        tool_name: str,
        handler: Callable[..., Any],
    ) -> None:
        """Register a handler for a specific tool.

        Args:
            tool_name: Name of the tool
            handler: Async function to handle the tool call
        """
        self._handlers[tool_name] = handler

    def register_server(
        self,
        server_name: str,
        handler: Callable[..., Any],
    ) -> None:
        """Register a handler for all tools from a server.

        Args:
            server_name: Name of the MCP server
            handler: Async function to handle tool calls for this server
        """
        self._server_handlers[server_name] = handler

    def set_fallback(self, handler: Callable[..., Any]) -> None:
        """Set a fallback handler for unregistered tools.

        Args:
            handler: Async function to handle unregistered tool calls
        """
        self._fallback_handler = handler

    async def route(
        self,
        tool_name: str,
        parameters: dict[str, Any],
        server_name: str | None = None,
    ) -> dict[str, Any]:
        """Route a tool call to the appropriate handler.

        Args:
            tool_name: Name of the tool to invoke
            parameters: Parameters for the tool
            server_name: Optional server name for routing

        Returns:
            Result from the tool handler
        """
        # Try tool-specific handler first
        if tool_name in self._handlers:
            return await self._handlers[tool_name](parameters)

        # Try server-specific handler
        if server_name and server_name in self._server_handlers:
            return await self._server_handlers[server_name](tool_name, parameters)

        # Use fallback if available
        if self._fallback_handler:
            return await self._fallback_handler(tool_name, parameters)

        # No handler found
        return {
            "error": f"No handler registered for tool: {tool_name}",
            "status": "unhandled",
        }

    def get_registered_tools(self) -> list[str]:
        """Get list of registered tool names.

        Returns:
            List of tool names with registered handlers
        """
        return list(self._handlers.keys())

    def get_registered_servers(self) -> list[str]:
        """Get list of registered server names.

        Returns:
            List of server names with registered handlers
        """
        return list(self._server_handlers.keys())


# Default handlers for common operations
async def file_read_handler(params: dict[str, Any]) -> dict[str, Any]:
    """Default handler for file read operations."""
    from pathlib import Path

    path = params.get("path")
    if not path:
        return {"error": "No path provided"}

    file_path = Path(path)
    if not file_path.exists():
        return {"error": f"File not found: {path}"}

    try:
        content = file_path.read_text()
        return {"content": content, "path": path}
    except (OSError, UnicodeDecodeError) as e:
        return {"error": f"Failed to read file: {e}"}


async def file_search_handler(params: dict[str, Any]) -> dict[str, Any]:
    """Default handler for file search operations."""
    from pathlib import Path

    pattern = params.get("pattern", "*")
    root = params.get("root", ".")
    max_results = params.get("max_results", 20)

    root_path = Path(root)
    if not root_path.exists():
        return {"error": f"Root path not found: {root}"}

    results = []
    try:
        for match in root_path.glob(pattern):
            if match.is_file():
                results.append(str(match))
                if len(results) >= max_results:
                    break
    except OSError as e:
        return {"error": f"Failed to search files: {e}"}

    return {"files": results, "count": len(results)}


def create_default_router() -> MCPRouter:
    """Create a router with default handlers.

    Returns:
        MCPRouter with common handlers registered
    """
    router = MCPRouter()
    router.register_tool("file_read", file_read_handler)
    router.register_tool("file_search", file_search_handler)
    return router
