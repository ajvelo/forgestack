"""MCP configuration loader."""

import json
from pathlib import Path
from typing import Any


class MCPLoader:
    """Loads MCP configuration from repositories.

    MCP (Model Context Protocol) configuration is typically stored in:
    - .mcp.json
    - mcp.json
    - .mcp/config.json

    The configuration describes available MCP servers and tools
    for the repository.
    """

    # Common MCP config file locations
    CONFIG_FILES = [
        ".mcp.json",
        "mcp.json",
        ".mcp/config.json",
        ".claude/mcp.json",
    ]

    def __init__(self) -> None:
        """Initialize the MCP loader."""
        pass

    def find_config(self, repo_path: Path) -> Path | None:
        """Find MCP configuration file in a repository.

        Args:
            repo_path: Path to the repository

        Returns:
            Path to config file or None if not found
        """
        for config_name in self.CONFIG_FILES:
            config_path = repo_path / config_name
            if config_path.exists():
                return config_path
        return None

    def load_config(self, repo_path: Path) -> dict[str, Any]:
        """Load MCP configuration for a repository.

        Args:
            repo_path: Path to the repository

        Returns:
            Dictionary with MCP configuration, empty if not found
        """
        config_path = self.find_config(repo_path)
        if not config_path:
            return {}

        try:
            with open(config_path, "r") as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError) as e:
            # Log warning but don't fail
            return {"_error": str(e)}

    def get_servers(self, config: dict[str, Any]) -> list[dict[str, Any]]:
        """Extract server configurations from MCP config.

        Only returns stdio-based servers (those with a command field).
        HTTP and SSE servers are not supported yet and are skipped.

        Args:
            config: Loaded MCP configuration

        Returns:
            List of server configurations (stdio servers only)
        """
        servers = []

        # Handle different config formats
        if "mcpServers" in config:
            # Claude Code format
            for name, server_config in config["mcpServers"].items():
                # Only include stdio servers (those with a command)
                server_type = server_config.get("type", "stdio")
                command = server_config.get("command")

                # Skip HTTP/SSE servers - not supported yet
                if server_type != "stdio" or not command:
                    continue

                servers.append({
                    "name": name,
                    "command": command,
                    "args": server_config.get("args", []),
                    "env": server_config.get("env", {}),
                })
        elif "servers" in config:
            # Alternative format - filter to only include servers with command
            servers = [
                s for s in config["servers"]
                if s.get("command") and isinstance(s.get("command"), str)
            ]

        return servers

    def get_tools(self, config: dict[str, Any]) -> list[dict[str, Any]]:
        """Extract tool definitions from MCP config.

        Args:
            config: Loaded MCP configuration

        Returns:
            List of tool definitions
        """
        tools = []

        if "tools" in config:
            tools = config["tools"]

        return tools


# Common MCP server types for reference
MCP_SERVER_TYPES = {
    "dart-analyzer": {
        "description": "Dart/Flutter code analysis",
        "capabilities": ["analyze", "format", "fix"],
    },
    "sentry": {
        "description": "Error tracking and monitoring",
        "capabilities": ["list-errors", "get-error-details"],
    },
    "posthog": {
        "description": "Product analytics",
        "capabilities": ["query", "events", "insights"],
    },
    "github": {
        "description": "GitHub integration",
        "capabilities": ["issues", "prs", "repos"],
    },
}
