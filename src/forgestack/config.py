"""Configuration management for ForgeStack."""

import os
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field, ValidationError


class AnthropicConfig(BaseModel):
    """Anthropic API configuration."""

    env_var: str = "ANTHROPIC_API_KEY"

    def get_api_key(self) -> str:
        """Get API key from environment variable."""
        api_key = os.environ.get(self.env_var)
        if not api_key:
            raise ValueError(
                f"Environment variable '{self.env_var}' not set. "
                f"Please set it in your shell profile (e.g., ~/.zshrc):\n"
                f'  export {self.env_var}="sk-ant-xxxxx"'
            )
        return api_key


class OrchestratorConfig(BaseModel):
    """Orchestrator configuration."""

    max_rounds: int = Field(default=3, ge=1, le=10)
    consensus_threshold: float = Field(default=0.92, ge=0.0, le=1.0)


class AgentConfig(BaseModel):
    """Individual agent configuration."""

    model: str
    temperature: float = Field(default=0.5, ge=0.0, le=1.0)
    max_tokens: int = Field(default=4096, ge=1)


class AgentsConfig(BaseModel):
    """All agents configuration."""

    generator: AgentConfig
    critic: AgentConfig
    synthesizer: AgentConfig


class PersistenceConfig(BaseModel):
    """Persistence layer configuration."""

    database_path: str = "./data/forgestack.db"
    enable_learning: bool = True

    def get_database_path(self) -> Path:
        """Get absolute database path."""
        return Path(self.database_path).expanduser().resolve()


class MCPServerConfig(BaseModel):
    """Configuration for an individual MCP server."""

    command: str
    args: list[str] = Field(default_factory=list)
    env: dict[str, str] = Field(default_factory=dict)
    optional: bool = Field(
        default=False,
        description="If true, connection failures are logged at debug level instead of warning",
    )


class MCPConfig(BaseModel):
    """MCP integration configuration."""

    timeout_seconds: int = Field(default=30, ge=1)
    max_retries: int = Field(default=3, ge=0)
    servers: dict[str, MCPServerConfig] = Field(default_factory=dict)


class DiscoveryConfig(BaseModel):
    """Auto-discovery configuration for a GitHub organization or user."""

    github_org: str = ""
    enabled: bool = False
    cache_ttl_minutes: int = 60


class CodebaseConfig(BaseModel):
    """Codebase repositories configuration."""

    repos: dict[str, str] = Field(default_factory=dict)
    design_system_repo_key: str | None = Field(
        default=None,
        description=(
            "Optional repo key that holds a design system. When set, UI-related "
            "tasks will receive a summary of that repo's components and theme as "
            "additional context."
        ),
    )

    def get_repo_path(self, repo_key: str) -> Path:
        """Get absolute path for a repository."""
        if repo_key not in self.repos:
            available = ", ".join(self.repos.keys())
            raise ValueError(f"Unknown repository '{repo_key}'. Available: {available}")
        return Path(self.repos[repo_key]).expanduser().resolve()

    def list_repos(self) -> list[str]:
        """List all configured repository keys."""
        return list(self.repos.keys())


class ForgeStackConfig(BaseModel):
    """Main ForgeStack configuration."""

    anthropic: AnthropicConfig = Field(default_factory=AnthropicConfig)
    orchestrator: OrchestratorConfig = Field(default_factory=OrchestratorConfig)
    agents: AgentsConfig
    persistence: PersistenceConfig = Field(default_factory=PersistenceConfig)
    mcp: MCPConfig = Field(default_factory=MCPConfig)
    codebase: CodebaseConfig = Field(default_factory=CodebaseConfig)
    discovery: DiscoveryConfig = Field(default_factory=DiscoveryConfig)


def find_config_file() -> Path:
    """Find the config.yaml file."""
    # Check current directory first
    cwd_config = Path.cwd() / "config.yaml"
    if cwd_config.exists():
        return cwd_config

    # Check package directory
    package_dir = Path(__file__).parent.parent.parent
    package_config = package_dir / "config.yaml"
    if package_config.exists():
        return package_config

    raise FileNotFoundError(
        "config.yaml not found. Please create one in the current directory "
        "or in the ForgeStack package directory."
    )


def load_config(config_path: Path | None = None) -> ForgeStackConfig:
    """Load configuration from YAML file.

    Args:
        config_path: Optional path to config file. If None, auto-discovers.

    Returns:
        Parsed ForgeStackConfig

    Raises:
        FileNotFoundError: If config file not found
        ValueError: If config file is invalid
    """
    if config_path is None:
        config_path = find_config_file()

    with open(config_path) as f:
        raw_config: dict[str, Any] = yaml.safe_load(f)

    try:
        return ForgeStackConfig(**raw_config)
    except ValidationError as e:
        error_msg = str(e)
        # Add helpful hints for common errors
        if "MCPServerConfig" in error_msg:
            error_msg += (
                "\n\nHint: Check that all MCP servers in config.yaml have a valid "
                "'command' string field. The command cannot be null or empty."
            )
        raise ValueError(f"Invalid configuration in {config_path}:\n{error_msg}") from e


# Global config instance (lazy-loaded)
_config: ForgeStackConfig | None = None


def get_config() -> ForgeStackConfig:
    """Get the global configuration instance."""
    global _config
    if _config is None:
        _config = load_config()
    return _config


def reset_config() -> None:
    """Reset the global configuration (useful for testing)."""
    global _config
    _config = None
