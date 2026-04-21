"""Formatting utilities for ForgeStack output."""

from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.table import Table
from rich.syntax import Syntax

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from forgestack.orchestrator.engine import SessionResult
    from forgestack.agents.base import AgentResponse
    from forgestack.persistence.models import SessionRecord


console = Console()


def format_session_result(result: "SessionResult") -> Panel:
    """Format a session result for display.

    Args:
        result: The session result to format

    Returns:
        Rich Panel with formatted content
    """
    # Status indicator
    if result.passed_consensus:
        status = "[bold green]✓ Consensus Reached[/bold green]"
        border = "green"
    else:
        status = "[bold yellow]⚠ Max Rounds Reached[/bold yellow]"
        border = "yellow"

    # Format score with color
    score_color = "green" if result.final_score >= 0.92 else "yellow" if result.final_score >= 0.82 else "red"

    header = (
        f"{status}\n"
        f"[bold]Score:[/bold] [{score_color}]{result.final_score:.2f}[/{score_color}]  "
        f"[bold]Rounds:[/bold] {result.rounds_count}"
    )

    return Panel(
        header,
        title="[bold]Session Complete[/bold]",
        subtitle=f"Task: {result.task_type}",
        border_style=border,
    )


def format_agent_response(
    agent_type: str,
    content: str,
    round_number: int,
    score: float | None = None,
) -> Panel:
    """Format an agent response for display.

    Args:
        agent_type: Type of agent (generator, critic, synthesizer)
        content: Response content
        round_number: Round number
        score: Optional score (for critic)

    Returns:
        Rich Panel with formatted content
    """
    # Color based on agent type
    colors = {
        "generator": "green",
        "critic": "yellow",
        "synthesizer": "blue",
    }
    color = colors.get(agent_type, "white")

    title = f"[bold {color}]{agent_type.title()}[/bold {color}] (Round {round_number})"

    if score is not None:
        title += f" - Score: {score:.2f}"

    return Panel(
        Markdown(content),
        title=title,
        border_style=color,
    )


def format_score(score: float, threshold: float = 0.92) -> str:
    """Format a score with color based on threshold.

    Args:
        score: The score to format
        threshold: Consensus threshold

    Returns:
        Formatted score string with color markup
    """
    if score >= threshold:
        return f"[bold green]{score:.2f}[/bold green]"
    elif score >= threshold - 0.1:
        return f"[bold yellow]{score:.2f}[/bold yellow]"
    else:
        return f"[bold red]{score:.2f}[/bold red]"


def format_code(code: str, language: str = "dart") -> Syntax:
    """Format code with syntax highlighting.

    Args:
        code: The code to format
        language: Programming language

    Returns:
        Rich Syntax object
    """
    return Syntax(code, language, theme="monokai", line_numbers=True)


def format_history_table(sessions: "list[SessionRecord]") -> Table:
    """Format session history as a table.

    Args:
        sessions: List of session records

    Returns:
        Rich Table with session history
    """
    table = Table(title="Session History")
    table.add_column("Session ID", style="cyan")
    table.add_column("Repo", style="green")
    table.add_column("Task Type", style="yellow")
    table.add_column("Score", justify="right")
    table.add_column("Rounds", justify="right")
    table.add_column("Created", style="dim")

    for session in sessions:
        score_str = format_score(session.final_score)
        table.add_row(
            session.id[:8] + "...",
            session.repo_key,
            session.task_type,
            score_str,
            str(session.rounds_count),
            session.created_at.strftime("%Y-%m-%d %H:%M"),
        )

    return table


def format_repo_info(repo_info: dict) -> Panel:
    """Format repository information.

    Args:
        repo_info: Dictionary with repo information

    Returns:
        Rich Panel with repo info
    """
    lines = []
    for key, value in repo_info.items():
        if isinstance(value, bool):
            value = "[green]Yes[/green]" if value else "[red]No[/red]"
        lines.append(f"[bold]{key}:[/bold] {value}")

    return Panel(
        "\n".join(lines),
        title="Repository Info",
        border_style="cyan",
    )


def truncate_text(text: str, max_length: int = 100) -> str:
    """Truncate text with ellipsis.

    Args:
        text: Text to truncate
        max_length: Maximum length

    Returns:
        Truncated text
    """
    if len(text) <= max_length:
        return text
    return text[: max_length - 3] + "..."
