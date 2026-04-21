"""Logging utilities for ForgeStack."""

import logging
import sys
from pathlib import Path
from typing import Optional

from rich.console import Console
from rich.logging import RichHandler


# Default log format
LOG_FORMAT = "%(message)s"
LOG_DATE_FORMAT = "[%X]"

# Module-level console for rich output
console = Console()


def setup_logging(
    level: int = logging.INFO,
    log_file: Optional[Path] = None,
    rich_output: bool = True,
) -> None:
    """Set up logging configuration.

    Args:
        level: Logging level (default: INFO)
        log_file: Optional path to log file
        rich_output: Whether to use Rich for console output
    """
    handlers: list[logging.Handler] = []

    # Console handler
    if rich_output:
        console_handler = RichHandler(
            console=console,
            show_time=True,
            show_path=False,
            markup=True,
        )
    else:
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setFormatter(
            logging.Formatter(LOG_FORMAT, LOG_DATE_FORMAT)
        )

    console_handler.setLevel(level)
    handlers.append(console_handler)

    # File handler (if specified)
    if log_file:
        log_file.parent.mkdir(parents=True, exist_ok=True)
        file_handler = logging.FileHandler(log_file)
        file_handler.setFormatter(
            logging.Formatter(
                "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
            )
        )
        file_handler.setLevel(level)
        handlers.append(file_handler)

    # Configure root logger
    logging.basicConfig(
        level=level,
        handlers=handlers,
        force=True,
    )

    # Reduce noise from third-party libraries
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("anthropic").setLevel(logging.WARNING)


def get_logger(name: str) -> logging.Logger:
    """Get a logger with the given name.

    Args:
        name: Logger name (typically __name__)

    Returns:
        Configured logger instance
    """
    return logging.getLogger(name)


class ForgeStackLogger:
    """Custom logger with ForgeStack-specific methods."""

    def __init__(self, name: str) -> None:
        """Initialize the logger.

        Args:
            name: Logger name
        """
        self._logger = logging.getLogger(name)
        self._console = Console()

    def info(self, message: str) -> None:
        """Log an info message."""
        self._logger.info(message)

    def debug(self, message: str) -> None:
        """Log a debug message."""
        self._logger.debug(message)

    def warning(self, message: str) -> None:
        """Log a warning message."""
        self._logger.warning(message)

    def error(self, message: str) -> None:
        """Log an error message."""
        self._logger.error(message)

    def agent_start(self, agent_name: str, round_num: int) -> None:
        """Log agent starting work."""
        self._console.print(
            f"[dim]Round {round_num}:[/dim] [bold]{agent_name}[/bold] working..."
        )

    def agent_complete(self, agent_name: str, score: Optional[float] = None) -> None:
        """Log agent completing work."""
        if score is not None:
            self._console.print(
                f"[green]✓[/green] {agent_name} complete - Score: [bold]{score:.2f}[/bold]"
            )
        else:
            self._console.print(f"[green]✓[/green] {agent_name} complete")

    def consensus_reached(self, score: float, threshold: float) -> None:
        """Log consensus being reached."""
        self._console.print(
            f"\n[bold green]✓ Consensus reached![/bold green] "
            f"Score {score:.2f} >= {threshold}"
        )

    def consensus_not_reached(self, score: float, threshold: float) -> None:
        """Log consensus not being reached."""
        self._console.print(
            f"[yellow]Score {score:.2f} < {threshold}. Revising...[/yellow]"
        )

    def session_complete(self, session_id: str) -> None:
        """Log session completion."""
        self._console.print(f"\n[dim]Session ID: {session_id}[/dim]")
