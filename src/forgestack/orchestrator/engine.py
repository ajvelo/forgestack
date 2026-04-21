"""ForgeStack Engine - Main orchestration logic."""

import logging
import uuid
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from rich.console import Console
from rich.panel import Panel

from forgestack.agents.base import AgentContext
from forgestack.agents.critic import CriticAgent
from forgestack.agents.generator import GeneratorAgent
from forgestack.agents.synthesizer import SynthesizerAgent
from forgestack.codebase.discovery import RepoDiscovery
from forgestack.codebase.reader import CodebaseReader
from forgestack.codebase.repos import RepoResolver
from forgestack.config import ForgeStackConfig
from forgestack.mcp.client import MCPClient
from forgestack.orchestrator.critique_round import CritiqueResult, CritiqueRound
from forgestack.persistence.database import SessionDatabase
from forgestack.persistence.models import AgentResponseRecord, SessionRecord
from forgestack.utils.formatting import format_agent_response

logger = logging.getLogger(__name__)


@dataclass
class SessionResult:
    """Result of a ForgeStack session."""

    session_id: str
    repo_key: str
    task_type: str
    task_description: str
    final_output: str
    final_score: float
    rounds_count: int
    passed_consensus: bool
    created_at: datetime


class ForgeStackEngine:
    """Main ForgeStack orchestration engine.

    The engine coordinates:
    1. Repository resolution and context gathering
    2. MCP client initialization for the target repo
    3. Agent creation and configuration
    4. Critique loop execution
    5. Final synthesis
    6. Session persistence
    """

    def __init__(self, config: ForgeStackConfig) -> None:
        """Initialize the ForgeStack engine.

        Args:
            config: ForgeStack configuration
        """
        self.config = config
        self.console = Console()

        # Initialize components
        self.repo_resolver = RepoResolver(config)
        self.codebase_reader = CodebaseReader()
        self.mcp_client = MCPClient(config)
        self.database = SessionDatabase(config.persistence.get_database_path())

        # Initialize repo discovery if enabled
        self.discovery: RepoDiscovery | None = None
        if config.discovery.enabled:
            self.discovery = RepoDiscovery(
                github_org=config.discovery.github_org,
                cache_ttl_minutes=config.discovery.cache_ttl_minutes,
            )

        # Initialize agents
        self.generator = GeneratorAgent(config, mcp_client=self.mcp_client)
        self.critic = CriticAgent(config)
        self.synthesizer = SynthesizerAgent(config)

    async def shutdown(self) -> None:
        """Shutdown the engine and clean up resources."""
        self.console.print("[dim]Shutting down...[/dim]")
        await self.mcp_client.shutdown()

    async def run_session(
        self,
        repo_key: str,
        task_type: str,
        task_description: str,
        verbose: bool = False,
    ) -> SessionResult:
        """Run a complete ForgeStack session.

        Args:
            repo_key: Key identifying the target repository
            task_type: Type of task (code_improvement, feature, bugfix, etc.)
            task_description: Description of the task to perform
            verbose: Whether to show detailed output

        Returns:
            SessionResult with the session outcome
        """
        session_id = str(uuid.uuid4())
        created_at = datetime.now()

        self.console.print(
            Panel(
                f"[dim]Session ID:[/dim] {session_id}",
                title="[bold cyan]⚡ ForgeStack Session[/bold cyan]",
                border_style="cyan",
            )
        )

        # Step 1: Resolve repository
        self.console.print("\n[bold blue]━━━ Setup ━━━[/bold blue]")
        self.console.print("[dim]→[/dim] Resolving repository...")
        repo_path = self.repo_resolver.resolve(repo_key)
        self.console.print(f"  [green]✓[/green] {repo_path}")

        # Step 2: Gather codebase context
        self.console.print("[dim]→[/dim] Gathering codebase context...")
        codebase_summary = await self._gather_codebase_context(
            repo_path, task_type, task_description
        )
        self.console.print("  [green]✓[/green] Context gathered")

        # Step 3: Get design system context if relevant
        design_system_summary = None
        if self._is_ui_related(task_type, task_description):
            self.console.print("[dim]→[/dim] Loading design system context...")
            design_system_summary = await self._gather_design_system_context()
            self.console.print("  [green]✓[/green] Design system loaded")
        else:
            self.console.print("[dim]→ Skipping design system (not UI-related)[/dim]")

        # Step 4: Initialize MCP for the repo
        self.console.print("[dim]→[/dim] Initializing MCP tools...")
        mcp_tools = await self.mcp_client.initialize_for_repo(repo_path)
        self.console.print(f"  [green]✓[/green] Loaded {len(mcp_tools)} MCP tools")

        # Step 5: Create initial context
        initial_context = AgentContext(
            repo_key=repo_key,
            repo_path=repo_path,
            task_type=task_type,
            task_description=task_description,
            codebase_summary=codebase_summary,
            design_system_summary=design_system_summary,
            mcp_tools=mcp_tools,
        )

        # Step 6: Run critique loop
        self.console.print("\n[bold blue]━━━ Critique Loop ━━━[/bold blue]")
        critique_round = CritiqueRound(
            config=self.config,
            generator=self.generator,
            critic=self.critic,
        )
        critique_result = await critique_round.run(initial_context)

        # Step 7: Synthesize final output
        self.console.print("\n[bold blue]━━━ Synthesis ━━━[/bold blue]")
        self.console.print("[dim]Synthesizer working...[/dim]")
        synthesis_context = AgentContext(
            repo_key=repo_key,
            repo_path=repo_path,
            task_type=task_type,
            task_description=task_description,
            codebase_summary=codebase_summary,
            design_system_summary=design_system_summary,
            mcp_tools=mcp_tools,
            previous_output=critique_result.final_proposal,
            feedback=critique_result.final_feedback,
        )
        synthesis_response = await self.synthesizer.process(synthesis_context)
        self.console.print("[green]✓[/green] Synthesis complete")
        self.console.print(
            format_agent_response(
                agent_type="synthesizer",
                content=synthesis_response.content,
                round_number=critique_result.total_rounds,
                score=critique_result.final_score,
            )
        )

        # Step 8: Persist session
        self.console.print("\n[dim]→[/dim] Saving session...")
        await self._persist_session(
            session_id=session_id,
            repo_key=repo_key,
            task_type=task_type,
            task_description=task_description,
            critique_result=critique_result,
            final_output=synthesis_response.content,
            created_at=created_at,
        )
        self.console.print("  [green]✓[/green] Session saved")

        return SessionResult(
            session_id=session_id,
            repo_key=repo_key,
            task_type=task_type,
            task_description=task_description,
            final_output=synthesis_response.content,
            final_score=critique_result.final_score,
            rounds_count=critique_result.total_rounds,
            passed_consensus=critique_result.passed_consensus,
            created_at=created_at,
        )

    async def _gather_codebase_context(
        self,
        repo_path: Path,
        task_type: str,
        task_description: str = "",
    ) -> str:
        """Gather relevant codebase context for the task.

        This includes:
        - Basic repo info and structure
        - Dependencies (pubspec.yaml for Flutter/Dart, package.json for JS/TS, etc.)
        - Auto-discovered related repos from the organization
        - Backend API context if relevant
        """
        summary_parts = []

        # Get basic repo info
        repo_info = self.codebase_reader.get_repo_info(repo_path)
        summary_parts.append(f"Repository: {repo_path.name}")
        summary_parts.append(f"Structure: {repo_info.get('structure', 'Unknown')}")

        # Collect dependency manifests for common stacks
        manifest_files = [
            "pubspec.yaml",  # Flutter / Dart
            "package.json",  # JS / TS
            "pyproject.toml",  # Python
            "Cargo.toml",  # Rust
            "go.mod",  # Go
        ]
        for manifest in manifest_files:
            contents = self.codebase_reader.read_file(repo_path / manifest)
            if contents:
                summary_parts.append(f"\nDependencies ({manifest} excerpt):\n{contents[:1000]}")
                break

        # Get lib structure
        lib_structure = self.codebase_reader.list_directory(repo_path / "lib")
        if lib_structure:
            summary_parts.append(f"\nLib structure:\n{lib_structure}")

        # Auto-discover related repos if enabled
        if self.discovery:
            try:
                self.console.print("  [dim]Discovering related repos...[/dim]")
                discovered = await self.discovery.gather_full_context(
                    task_description=task_description,
                    task_type=task_type,
                    current_repo_path=repo_path,
                )
                discovery_context = self.discovery.format_context_for_prompt(discovered)
                if discovery_context:
                    summary_parts.append(f"\n{discovery_context}")
                    self.console.print(f"  [dim]Found {len(discovered.repos)} related repos[/dim]")
            except Exception as e:
                logger.debug(f"Discovery failed (non-fatal): {e}")

        return "\n".join(summary_parts)

    async def _gather_design_system_context(self) -> str | None:
        """Gather context from the configured design system repo, if any.

        Returns None unless `codebase.design_system_repo_key` is set in config
        and points to a repo that exists locally.
        """
        design_system_key = self.config.codebase.design_system_repo_key
        if not design_system_key:
            return None

        try:
            ds_path = self.repo_resolver.resolve(design_system_key)
            if not ds_path.exists():
                return None

            summary_parts = [f"Design System: {design_system_key}"]

            # Common component locations across stacks
            candidate_component_dirs = [
                ds_path / "lib" / "src" / "components",  # Flutter/Dart
                ds_path / "src" / "components",  # JS/TS
                ds_path / "components",  # generic
            ]
            for components_dir in candidate_component_dirs:
                if components_dir.exists():
                    components = self.codebase_reader.list_directory(components_dir)
                    summary_parts.append(f"\nAvailable components:\n{components}")
                    break

            # Common theme locations
            candidate_theme_dirs = [
                ds_path / "lib" / "src" / "theme",
                ds_path / "src" / "theme",
                ds_path / "theme",
            ]
            for theme_dir in candidate_theme_dirs:
                if theme_dir.exists():
                    theme_files = self.codebase_reader.list_directory(theme_dir)
                    summary_parts.append(f"\nTheme files:\n{theme_files}")
                    break

            return "\n".join(summary_parts)

        except (OSError, ValueError) as e:
            logger.debug(f"Failed to gather design system context: {e}")
            return None

    def _is_ui_related(self, task_type: str, task_description: str) -> bool:
        """Check if the task is UI-related."""
        ui_keywords = [
            "ui",
            "widget",
            "screen",
            "page",
            "component",
            "button",
            "design",
            "layout",
            "theme",
            "style",
            "color",
            "icon",
            "animation",
            "navigation",
            "dialog",
            "modal",
            "form",
        ]

        combined = f"{task_type} {task_description}".lower()
        return any(keyword in combined for keyword in ui_keywords)

    async def _persist_session(
        self,
        session_id: str,
        repo_key: str,
        task_type: str,
        task_description: str,
        critique_result: CritiqueResult,
        final_output: str,
        created_at: datetime,
    ) -> None:
        """Persist the session to the database."""
        # Build agent response records
        agent_responses = []
        for round_result in critique_result.rounds:
            agent_responses.append(
                AgentResponseRecord(
                    session_id=session_id,
                    agent_type="generator",
                    round_number=round_result.round_number,
                    content=round_result.generator_response.content,
                    score=None,
                )
            )
            agent_responses.append(
                AgentResponseRecord(
                    session_id=session_id,
                    agent_type="critic",
                    round_number=round_result.round_number,
                    content=round_result.critic_response.content,
                    score=round_result.score,
                )
            )

        # Add synthesizer response
        agent_responses.append(
            AgentResponseRecord(
                session_id=session_id,
                agent_type="synthesizer",
                round_number=critique_result.total_rounds,
                content=final_output,
                score=critique_result.final_score,
            )
        )

        # Create session record
        session = SessionRecord(
            id=session_id,
            repo_key=repo_key,
            task_type=task_type,
            task_description=task_description,
            final_output=final_output,
            final_score=critique_result.final_score,
            rounds_count=critique_result.total_rounds,
            created_at=created_at,
            agent_responses=agent_responses,
        )

        await self.database.save_session(session)
