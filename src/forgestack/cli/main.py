"""ForgeStack CLI - Main entry point."""

import asyncio
from enum import Enum
from pathlib import Path
from typing import TYPE_CHECKING, Annotated, Optional

import typer

if TYPE_CHECKING:
    from forgestack.orchestrator.engine import SessionResult
    from forgestack.persistence.models import SessionRecord
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from forgestack.config import get_config
from forgestack.orchestrator.engine import ForgeStackEngine
from forgestack.persistence.database import SessionDatabase
from forgestack.prompts import get_prompts_dir, load_task_prompt
from forgestack.utils.formatting import format_session_result

app = typer.Typer(
    name="forgestack",
    help="Multi-agent Claude critique engine for code analysis",
    rich_markup_mode="rich",
    add_completion=False,
)
console = Console()


@app.callback(invoke_without_command=True)
def main(
    ctx: typer.Context,
    help_flag: Annotated[
        bool,
        typer.Option("--help", "-h", help="Show this help message"),
    ] = False,
) -> None:
    """Multi-agent Claude critique engine for code analysis."""
    if ctx.invoked_subcommand is None or help_flag:
        console.print()
        console.print(
            Panel(
                "[bold]Generator[/bold] → [bold]Critic[/bold] → [bold]Synthesizer[/bold]\n"
                "Critique loop until consensus ≥0.85 is reached",
                title="[bold cyan]ForgeStack[/bold cyan]",
                subtitle="Multi-agent Claude critique engine",
                border_style="cyan",
            )
        )

        # Task types table
        task_table = Table(box=None, show_header=False, padding=(0, 2))
        task_table.add_column("Task", style="green", width=18)
        task_table.add_column("Description")
        task_table.add_row("code_improvement", "Refactoring, cleanup, optimization")
        task_table.add_row("feature", "New functionality implementation")
        task_table.add_row("bugfix", "Fix defects and crashes")
        task_table.add_row("architecture", "Design proposals and patterns")
        task_table.add_row("exploration", "Analysis and discovery")

        console.print(Panel(task_table, title="[bold]Task Types[/bold]", border_style="dim"))

        # Commands table
        cmd_table = Table(box=None, show_header=False, padding=(0, 2))
        cmd_table.add_column("Command", style="cyan", width=12)
        cmd_table.add_column("Description")
        cmd_table.add_row("run", "Run a critique session")
        cmd_table.add_row("apply", "Apply changes from output file")
        cmd_table.add_row("repos", "List configured repositories")
        cmd_table.add_row("history", "View session history")
        cmd_table.add_row("export", "Export a session to file")
        cmd_table.add_row("config-info", "Show current configuration")

        console.print(Panel(cmd_table, title="[bold]Commands[/bold]", border_style="dim"))

        # Examples
        console.print(Panel(
            '[dim]$[/dim] forgestack run -r app -t exploration\n'
            '[dim]  (loads from prompts/.prompt.txt)[/dim]\n'
            '[dim]$[/dim] forgestack run -r app -t bugfix "Fix login crash"\n'
            '[dim]$[/dim] forgestack apply output/forgestack-abc123.md\n'
            '[dim]$[/dim] forgestack repos',
            title="[bold]Examples[/bold]",
            border_style="dim",
        ))

        console.print("[dim]Run 'forgestack <command> --help' for details[/dim]")
        raise typer.Exit()


class TaskType(str, Enum):
    """Supported task types."""

    CODE_IMPROVEMENT = "code_improvement"  # Refactoring, cleanup, optimization
    FEATURE = "feature"  # New functionality implementation
    BUGFIX = "bugfix"  # Fix defects and crashes
    ARCHITECTURE = "architecture"  # Design proposals and patterns
    EXPLORATION = "exploration"  # Analysis and discovery


class ExportFormat(str, Enum):
    """Supported export formats."""

    MARKDOWN = "markdown"
    JSON = "json"


@app.command()
def run(
    repo: Annotated[
        str,
        typer.Option(
            "--repo", "-r",
            help="Repository key from config.yaml (use 'forgestack repos' to list)",
        ),
    ],
    task: Annotated[
        TaskType,
        typer.Option(
            "--task", "-t",
            help="Task type: code_improvement|feature|bugfix|architecture|exploration",
        ),
    ],
    description: Annotated[
        Optional[str],
        typer.Argument(help="Natural language description (or use --prompt-file)"),
    ] = None,
    prompt_file: Annotated[
        str,
        typer.Option(
            "--prompt-file", "-p",
            help="Load description from file in prompts/ directory",
        ),
    ] = ".prompt.txt",
    verbose: Annotated[
        bool,
        typer.Option("--verbose", "-v", help="Show detailed agent responses"),
    ] = False,
) -> None:
    """
    Run a multi-agent critique session on a repository.

    The Generator proposes solutions, the Critic evaluates them (0-10 score),
    and the loop continues until score ≥0.85 or max rounds reached.
    The Synthesizer then produces the final output.

    You can provide the task description either as an argument or via --prompt-file.
    By default, it loads from prompts/.prompt.txt if no description is provided.

    Examples:
        forgestack run -r app -t exploration
        forgestack run -r app -t bugfix "Fix login crash"
        forgestack run -r app -t feature --prompt-file my_feature.txt
    """
    config = get_config()

    # Resolve description: argument takes priority, then prompt file
    if description:
        task_description = description
    else:
        try:
            task_description = load_task_prompt(prompt_file)
            console.print(f"[dim]Loaded prompt from: {get_prompts_dir() / prompt_file}[/dim]")
        except FileNotFoundError as e:
            console.print(f"[red]Error:[/red] {e}")
            console.print(
                f"\n[yellow]Tip:[/yellow] Create the file or provide a description:\n"
                f"  forgestack run -r {repo} -t {task.value} \"Your description here\""
            )
            raise typer.Exit(1)
        except ValueError as e:
            console.print(f"[red]Error:[/red] {e}")
            raise typer.Exit(1)

    # Validate repository
    try:
        repo_path = config.codebase.get_repo_path(repo)
    except ValueError as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1)

    if not repo_path.exists():
        console.print(
            f"[red]Error:[/red] Repository path does not exist: {repo_path}"
        )
        raise typer.Exit(1)

    # Truncate description for display if too long
    display_desc = task_description[:200] + "..." if len(task_description) > 200 else task_description

    console.print(
        Panel(
            f"[bold]Repository:[/bold] {repo} ({repo_path})\n"
            f"[bold]Task Type:[/bold] {task.value}\n"
            f"[bold]Description:[/bold] {display_desc}",
            title="ForgeStack Session",
            border_style="blue",
        )
    )

    # Run the critique loop
    async def run_with_cleanup() -> "SessionResult":
        """Run session and ensure proper cleanup."""
        engine = ForgeStackEngine(config)
        try:
            return await engine.run_session(
                repo_key=repo,
                task_type=task.value,
                task_description=task_description,
                verbose=verbose,
            )
        finally:
            await engine.shutdown()

    try:
        result = asyncio.run(run_with_cleanup())

        # Display results
        console.print()
        console.print(format_session_result(result))

        # Auto-save output to output folder
        output_dir = Path("output")
        output_dir.mkdir(exist_ok=True)
        output_path = output_dir / f"forgestack-{result.session_id[:8]}.md"

        # Save the synthesizer output for later application
        output_content = _generate_apply_output(result)
        with open(output_path, "w") as f:
            f.write(output_content)

        console.print(f"\n[green]✓[/green] Output saved to: {output_path}")
        console.print(f"[dim]Run 'forgestack apply {output_path}' to apply changes[/dim]")

        # Show session ID for future reference
        console.print(
            f"\n[dim]Session ID: {result.session_id}[/dim]"
        )
        console.print(
            f"[dim]Consensus Score: {result.final_score:.2f}[/dim]"
        )

    except Exception as e:
        console.print(f"[red]Error during session:[/red] {e}")
        if verbose:
            console.print_exception()
        raise typer.Exit(1)


@app.command()
def history(
    last: Annotated[
        int,
        typer.Option("--last", "-n", help="Show last N sessions"),
    ] = 10,
    repo: Annotated[
        Optional[str],
        typer.Option("--repo", "-r", help="Filter by repository"),
    ] = None,
) -> None:
    """View session history."""
    config = get_config()
    db = SessionDatabase(config.persistence.get_database_path())

    try:
        sessions = asyncio.run(db.get_sessions(limit=last, repo_filter=repo))
    except Exception as e:
        console.print(f"[red]Error loading history:[/red] {e}")
        raise typer.Exit(1)

    if not sessions:
        console.print("[dim]No sessions found.[/dim]")
        return

    table = Table(title="Session History")
    table.add_column("Session ID", style="cyan")
    table.add_column("Repo", style="green")
    table.add_column("Task Type", style="yellow")
    table.add_column("Score", justify="right")
    table.add_column("Rounds", justify="right")
    table.add_column("Created", style="dim")

    for session in sessions:
        score_color = "green" if session.final_score >= 0.92 else "yellow"
        table.add_row(
            session.id[:8] + "...",
            session.repo_key,
            session.task_type,
            f"[{score_color}]{session.final_score:.2f}[/{score_color}]",
            str(session.rounds_count),
            session.created_at.strftime("%Y-%m-%d %H:%M"),
        )

    console.print(table)


@app.command("export")
def export_session(
    session_id: Annotated[
        str,
        typer.Option("--session-id", "-s", help="Session ID to export"),
    ],
    format: Annotated[
        ExportFormat,
        typer.Option("--format", "-f", help="Export format"),
    ] = ExportFormat.MARKDOWN,
    output: Annotated[
        Optional[str],
        typer.Option("--output", "-o", help="Output file path"),
    ] = None,
) -> None:
    """Export a session to a file."""
    config = get_config()
    db = SessionDatabase(config.persistence.get_database_path())

    try:
        session = asyncio.run(db.get_session(session_id))
    except Exception as e:
        console.print(f"[red]Error loading session:[/red] {e}")
        raise typer.Exit(1)

    if not session:
        console.print(f"[red]Session not found:[/red] {session_id}")
        raise typer.Exit(1)

    # Generate export content
    if format == ExportFormat.MARKDOWN:
        content = _export_markdown(session)
        default_ext = ".md"
    else:
        content = _export_json(session)
        default_ext = ".json"

    # Ensure output directory exists
    output_dir = Path("output")
    output_dir.mkdir(exist_ok=True)

    # Write to file
    if output:
        output_path = Path(output)
    else:
        output_path = output_dir / f"forgestack-{session.id[:8]}{default_ext}"

    with open(output_path, "w") as f:
        f.write(content)
    console.print(f"[green]Exported to:[/green] {output_path}")


def _export_markdown(session: "SessionRecord") -> str:
    """Export session to markdown format."""
    lines = [
        f"# ForgeStack Session: {session.id}",
        "",
        f"**Repository:** {session.repo_key}",
        f"**Task Type:** {session.task_type}",
        f"**Created:** {session.created_at.isoformat()}",
        f"**Final Score:** {session.final_score:.2f}",
        f"**Rounds:** {session.rounds_count}",
        "",
        "## Task Description",
        "",
        session.task_description,
        "",
        "## Final Output",
        "",
        session.final_output,
        "",
    ]

    if session.agent_responses:
        lines.append("## Agent Responses")
        lines.append("")
        for response in session.agent_responses:
            lines.append(f"### {response.agent_type.title()} (Round {response.round_number})")
            lines.append("")
            lines.append(response.content)
            lines.append("")

    return "\n".join(lines)


def _export_json(session: "SessionRecord") -> str:
    """Export session to JSON format."""
    import json

    data = {
        "id": session.id,
        "repo_key": session.repo_key,
        "task_type": session.task_type,
        "task_description": session.task_description,
        "created_at": session.created_at.isoformat(),
        "final_score": session.final_score,
        "rounds_count": session.rounds_count,
        "final_output": session.final_output,
        "agent_responses": [
            {
                "agent_type": r.agent_type,
                "round_number": r.round_number,
                "content": r.content,
                "score": r.score,
            }
            for r in (session.agent_responses or [])
        ],
    }

    return json.dumps(data, indent=2)


def _generate_apply_output(result: "SessionResult") -> str:
    """Generate output file for the apply command.

    This creates a markdown file with metadata and the synthesizer output
    that can be parsed by the apply command.
    """
    lines = [
        "# ForgeStack Output",
        "",
        "<!-- FORGESTACK_METADATA",
        f"session_id: {result.session_id}",
        f"repo_key: {result.repo_key}",
        f"task_type: {result.task_type}",
        f"final_score: {result.final_score}",
        f"created_at: {result.created_at.isoformat()}",
        "-->",
        "",
        f"**Repository:** {result.repo_key}",
        f"**Task:** {result.task_type}",
        f"**Score:** {result.final_score:.2f}",
        "",
        "---",
        "",
        result.final_output,
    ]
    return "\n".join(lines)


def _parse_code_blocks(content: str) -> list[dict[str, str]]:
    """Parse code blocks from markdown content.

    Extracts code blocks with file paths from Claude/synthesizer output.
    Handles various natural output patterns:
    - ```dart:path/to/file.dart (inline path)
    - **File**: `path/to/file.dart` followed by code block
    - **File:** `path/to/file.dart` followed by code block
    - // File: path/to/file.dart comment in code block
    """
    import re

    blocks = []

    # Pattern 1: Code blocks with file path in language tag
    # ```dart:lib/src/foo.dart
    pattern1 = r"```(\w+):([^\n]+)\n(.*?)```"
    for match in re.finditer(pattern1, content, re.DOTALL):
        lang, file_path, code = match.groups()
        blocks.append({
            "language": lang,
            "file_path": file_path.strip(),
            "code": code.strip(),
        })

    # Pattern 2a: **File**: `path` (Claude's natural format - colon outside bold)
    # **File**: `lib/src/foo.dart`
    # **Action**: Create (optional line)
    # ```dart
    pattern2a = r"\*\*File\*\*:\s*`([^`]+)`[^\n]*\n+(?:\*\*Action\*\*:[^\n]*\n+)?```(\w+)\n(.*?)```"
    for match in re.finditer(pattern2a, content, re.DOTALL):
        file_path, lang, code = match.groups()
        # Avoid duplicates
        if not any(b["file_path"] == file_path.strip() for b in blocks):
            blocks.append({
                "language": lang,
                "file_path": file_path.strip(),
                "code": code.strip(),
            })

    # Pattern 2b: **File:** `path` (colon inside bold - legacy format)
    # **File:** `lib/src/foo.dart`
    # ```dart
    pattern2b = r"\*\*File:\*\*\s*`([^`]+)`\s*\n+```(\w+)\n(.*?)```"
    for match in re.finditer(pattern2b, content, re.DOTALL):
        file_path, lang, code = match.groups()
        if not any(b["file_path"] == file_path.strip() for b in blocks):
            blocks.append({
                "language": lang,
                "file_path": file_path.strip(),
                "code": code.strip(),
            })

    # Pattern 3: // File: path/to/file.dart comment at start of code block
    pattern3 = r"```(\w+)\n//\s*[Ff]ile:\s*([^\n]+)\n(.*?)```"
    for match in re.finditer(pattern3, content, re.DOTALL):
        lang, file_path, code = match.groups()
        if not any(b["file_path"] == file_path.strip() for b in blocks):
            blocks.append({
                "language": lang,
                "file_path": file_path.strip(),
                "code": code.strip(),
            })

    # Pattern 4: Numbered steps with file path
    # ### Step N: Description
    # **File**: `path/to/file.dart`
    pattern4 = r"###\s+Step\s+\d+[^\n]*\n\*\*File\*\*:\s*`([^`]+)`[^\n]*\n+(?:\*\*Action\*\*:[^\n]*\n+)?```(\w+)\n(.*?)```"
    for match in re.finditer(pattern4, content, re.DOTALL):
        file_path, lang, code = match.groups()
        if not any(b["file_path"] == file_path.strip() for b in blocks):
            blocks.append({
                "language": lang,
                "file_path": file_path.strip(),
                "code": code.strip(),
            })

    return blocks


@app.command()
def apply(
    output_file: Annotated[
        Path,
        typer.Argument(help="Path to ForgeStack output file"),
    ],
    dry_run: Annotated[
        bool,
        typer.Option("--dry-run", "-n", help="Show changes without applying"),
    ] = False,
    force: Annotated[
        bool,
        typer.Option("--force", "-f", help="Apply without confirmation"),
    ] = False,
) -> None:
    """Apply code changes from a ForgeStack output file.

    Parses the output file for code blocks with file paths and applies
    the changes to the repository.
    """
    if not output_file.exists():
        console.print(f"[red]Error:[/red] File not found: {output_file}")
        raise typer.Exit(1)

    content = output_file.read_text()

    # Parse metadata
    import re
    metadata_match = re.search(
        r"<!-- FORGESTACK_METADATA\n(.*?)\n-->",
        content,
        re.DOTALL,
    )

    if not metadata_match:
        console.print("[yellow]Warning:[/yellow] No ForgeStack metadata found in file")
        repo_key = None
    else:
        metadata_lines = metadata_match.group(1).split("\n")
        metadata = {}
        for line in metadata_lines:
            if ":" in line:
                key, value = line.split(":", 1)
                metadata[key.strip()] = value.strip()
        repo_key = metadata.get("repo_key")
        console.print(f"[dim]Session: {metadata.get('session_id', 'unknown')[:8]}...[/dim]")
        console.print(f"[dim]Repository: {repo_key}[/dim]")
        console.print(f"[dim]Score: {metadata.get('final_score', 'unknown')}[/dim]")

    # Get repo path
    if repo_key:
        config = get_config()
        try:
            repo_path = config.codebase.get_repo_path(repo_key)
        except ValueError:
            console.print(f"[yellow]Warning:[/yellow] Unknown repo '{repo_key}', using current directory")
            repo_path = Path.cwd()
    else:
        repo_path = Path.cwd()

    # Parse code blocks
    code_blocks = _parse_code_blocks(content)

    if not code_blocks:
        console.print("[yellow]No code blocks with file paths found in output.[/yellow]")
        console.print("[dim]Tip: The synthesizer output should include code blocks with file paths.[/dim]")
        console.print("[dim]Supported formats:[/dim]")
        console.print("[dim]  **File**: `lib/src/file.dart`[/dim]")
        console.print("[dim]  ```dart[/dim]")
        console.print("[dim]  // code[/dim]")
        console.print("[dim]  ```[/dim]")
        console.print("[dim]Or:[/dim]")
        console.print("[dim]  ```dart:lib/src/file.dart[/dim]")
        console.print("[dim]  // code[/dim]")
        console.print("[dim]  ```[/dim]")
        raise typer.Exit(0)

    console.print(f"\n[bold]Found {len(code_blocks)} code block(s) to apply:[/bold]\n")

    # Show changes
    for i, block in enumerate(code_blocks, 1):
        file_path = repo_path / block["file_path"]
        exists = file_path.exists()
        status = "[yellow]modify[/yellow]" if exists else "[green]create[/green]"

        console.print(f"  {i}. [{status}] {block['file_path']}")

        if dry_run:
            # Show preview
            preview_lines = block["code"].split("\n")[:10]
            preview = "\n".join(f"     {line}" for line in preview_lines)
            if len(block["code"].split("\n")) > 10:
                preview += "\n     ..."
            console.print(f"[dim]{preview}[/dim]\n")

    if dry_run:
        console.print("\n[dim]Dry run - no changes made. Remove --dry-run to apply.[/dim]")
        return

    # Confirm
    if not force:
        console.print()
        confirm = typer.confirm("Apply these changes?")
        if not confirm:
            console.print("[dim]Cancelled.[/dim]")
            raise typer.Exit(0)

    # Apply changes
    console.print("\n[bold]Applying changes...[/bold]\n")

    for block in code_blocks:
        file_path = repo_path / block["file_path"]

        # Create parent directories if needed
        file_path.parent.mkdir(parents=True, exist_ok=True)

        # Write file
        try:
            file_path.write_text(block["code"])
            console.print(f"  [green]✓[/green] {block['file_path']}")
        except Exception as e:
            console.print(f"  [red]✗[/red] {block['file_path']}: {e}")

    console.print("\n[green]✓ Changes applied successfully![/green]")
    console.print("[dim]Review the changes and commit when ready.[/dim]")


@app.command()
def repos() -> None:
    """List configured repositories."""
    config = get_config()

    table = Table(title="Configured Repositories")
    table.add_column("Key", style="cyan")
    table.add_column("Path", style="green")
    table.add_column("Status")

    for repo_key in config.codebase.list_repos():
        try:
            path = config.codebase.get_repo_path(repo_key)
            exists = path.exists()
            status = "[green]OK[/green]" if exists else "[red]Not Found[/red]"
            table.add_row(repo_key, str(path), status)
        except Exception as e:
            table.add_row(repo_key, "Error", f"[red]{e}[/red]")

    console.print(table)


@app.command()
def config_info() -> None:
    """Show current configuration."""
    config = get_config()

    console.print(Panel("[bold]ForgeStack Configuration[/bold]", border_style="blue"))

    console.print("\n[bold]Orchestrator:[/bold]")
    console.print(f"  Max Rounds: {config.orchestrator.max_rounds}")
    console.print(f"  Consensus Threshold: {config.orchestrator.consensus_threshold}")

    console.print("\n[bold]Agents:[/bold]")
    for name, agent_config in [
        ("Generator", config.agents.generator),
        ("Critic", config.agents.critic),
        ("Synthesizer", config.agents.synthesizer),
    ]:
        console.print(f"  {name}:")
        console.print(f"    Model: {agent_config.model}")
        console.print(f"    Temperature: {agent_config.temperature}")
        console.print(f"    Max Tokens: {agent_config.max_tokens}")

    console.print("\n[bold]Persistence:[/bold]")
    console.print(f"  Database: {config.persistence.database_path}")
    console.print(f"  Learning: {'Enabled' if config.persistence.enable_learning else 'Disabled'}")


if __name__ == "__main__":
    app()
