"""Critique round - manages the Generator/Critic feedback loop."""

import hashlib
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from rich.console import Console

from forgestack.agents.base import AgentContext, AgentResponse
from forgestack.agents.critic import CriticAgent
from forgestack.agents.generator import GeneratorAgent
from forgestack.config import ForgeStackConfig
from forgestack.utils.formatting import format_agent_response


@dataclass
class RoundResult:
    """Result of a single critique round."""

    round_number: int
    generator_response: AgentResponse
    critic_response: AgentResponse
    score: float
    passed: bool


@dataclass
class CritiqueResult:
    """Final result of the critique loop."""

    rounds: list[RoundResult] = field(default_factory=list)
    final_proposal: str = ""
    final_score: float = 0.0
    final_feedback: str = ""
    passed_consensus: bool = False
    total_rounds: int = 0


class CritiqueRound:
    """Manages the Generator/Critic critique loop.

    The critique loop continues until:
    - The Critic's score >= consensus_threshold (0.92 by default)
    - OR max_rounds is reached

    Each round:
    1. Generator produces/revises proposal
    2. Critic evaluates and scores
    3. If score < threshold, Generator revises based on feedback
    """

    def __init__(
        self,
        config: ForgeStackConfig,
        generator: GeneratorAgent,
        critic: CriticAgent,
        on_round_complete: Callable[[RoundResult], None] | None = None,
    ) -> None:
        """Initialize the critique round manager.

        Args:
            config: ForgeStack configuration
            generator: The Generator agent
            critic: The Critic agent
            on_round_complete: Optional callback for each completed round
        """
        self.config = config
        self.generator = generator
        self.critic = critic
        self.on_round_complete = on_round_complete

        self.max_rounds = config.orchestrator.max_rounds
        self.consensus_threshold = config.orchestrator.consensus_threshold

        self.console = Console()

    def _compute_proposal_hash(self, content: str) -> str:
        """Compute a short hash to verify proposals change between rounds."""
        return hashlib.sha256(content.encode()).hexdigest()[:8]

    async def run(self, initial_context: AgentContext) -> CritiqueResult:
        """Run the critique loop.

        Args:
            initial_context: The initial context for the task

        Returns:
            CritiqueResult with all rounds and final output
        """
        result = CritiqueResult()
        context = initial_context
        evaluation_history: list[dict[str, Any]] = []

        for round_num in range(1, self.max_rounds + 1):
            context.round_number = round_num

            # Log round start
            self.console.print(
                f"\n[bold blue]━━━ Round {round_num}/{self.max_rounds} ━━━[/bold blue]"
            )

            # Step 1: Generator produces/revises proposal
            self.console.print("[dim]Generator working...[/dim]")
            generator_response = await self.generator.process(context)
            proposal_hash = self._compute_proposal_hash(generator_response.content)
            self.console.print(
                f"[green]✓[/green] Generator complete [dim](hash: {proposal_hash})[/dim]"
            )
            self.console.print(
                format_agent_response(
                    agent_type="generator",
                    content=generator_response.content,
                    round_number=round_num,
                )
            )

            # Step 2: Critic evaluates
            self.console.print("[dim]Critic evaluating...[/dim]")
            critic_context = AgentContext(
                repo_key=context.repo_key,
                repo_path=context.repo_path,
                task_type=context.task_type,
                task_description=context.task_description,
                codebase_summary=context.codebase_summary,
                design_system_summary=context.design_system_summary,
                mcp_tools=context.mcp_tools,
                previous_output=generator_response.content,
                round_number=round_num,
                evaluation_history=evaluation_history if evaluation_history else None,
            )
            critic_response = await self.critic.process(critic_context)
            score = self.critic.get_normalized_score(critic_response)
            self.console.print("[green]✓[/green] Critic complete")
            self.console.print(
                format_agent_response(
                    agent_type="critic",
                    content=critic_response.content,
                    round_number=round_num,
                    score=score,
                )
            )

            # Record round result
            round_result = RoundResult(
                round_number=round_num,
                generator_response=generator_response,
                critic_response=critic_response,
                score=score,
                passed=score >= self.consensus_threshold,
            )
            result.rounds.append(round_result)

            # Track evaluation history for next round's Critic context.
            # `critic.process()` attaches the parsed evaluation to the
            # response; if the subclass didn't provide one, degrade
            # gracefully with empty lists rather than reaching across the
            # abstraction to call `_parse_evaluation` ourselves.
            evaluation = getattr(critic_response, "evaluation", None)
            evaluation_history.append(
                {
                    "round": round_num,
                    "score": score,
                    "weaknesses": evaluation.weaknesses if evaluation else [],
                    "recommendations": evaluation.recommendations if evaluation else [],
                    "proposal_hash": proposal_hash,
                }
            )

            # Log score delta if not first round
            if len(evaluation_history) > 1:
                prev_score = evaluation_history[-2]["score"]
                delta = score - prev_score
                delta_str = f"+{delta:.2f}" if delta >= 0 else f"{delta:.2f}"
                self.console.print(f"[dim]Score delta: {delta_str} (was {prev_score:.2f})[/dim]")

            # Callback if provided
            if self.on_round_complete:
                self.on_round_complete(round_result)

            # Check if we've reached consensus
            if score >= self.consensus_threshold:
                self.console.print(
                    f"\n[bold green]✓ Consensus reached![/bold green] "
                    f"Score {score:.2f} >= {self.consensus_threshold}"
                )
                result.passed_consensus = True
                result.final_proposal = generator_response.content
                result.final_score = score
                result.final_feedback = critic_response.content
                result.total_rounds = round_num
                return result

            # Prepare for next round with feedback
            self.console.print(
                f"[yellow]Score {score:.2f} < {self.consensus_threshold}. Revising...[/yellow]"
            )
            context = AgentContext(
                repo_key=context.repo_key,
                repo_path=context.repo_path,
                task_type=context.task_type,
                task_description=context.task_description,
                codebase_summary=context.codebase_summary,
                design_system_summary=context.design_system_summary,
                mcp_tools=context.mcp_tools,
                previous_output=generator_response.content,
                feedback=critic_response.content,
                round_number=round_num + 1,
                evaluation_history=evaluation_history,  # Pass history to Generator
            )

        # Max rounds reached without consensus
        self.console.print(
            f"\n[yellow]Max rounds ({self.max_rounds}) reached without consensus.[/yellow]"
        )

        # Use the last round's results
        last_round = result.rounds[-1]
        result.final_proposal = last_round.generator_response.content
        result.final_score = last_round.score
        result.final_feedback = last_round.critic_response.content
        result.total_rounds = self.max_rounds
        result.passed_consensus = False

        return result
