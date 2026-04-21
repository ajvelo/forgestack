"""Critic agent - evaluates and scores proposals."""

import re
from dataclasses import dataclass
from typing import Any

from forgestack.agents.base import AgentContext, AgentResponse, BaseAgent
from forgestack.config import ForgeStackConfig
from forgestack.prompts import load_prompt


@dataclass
class CriticEvaluation:
    """Structured evaluation from the Critic."""

    score: float
    feedback: str
    strengths: list[str]
    weaknesses: list[str]
    recommendations: list[str]


class CriticAgent(BaseAgent):
    """Critic agent that evaluates proposals.

    The Critic is responsible for:
    - Analyzing proposals for correctness
    - Checking compatibility with repo architecture
    - Assessing maintainability and complexity
    - Identifying edge cases and risks
    - Producing a score from 0-10
    - Providing actionable feedback for revisions
    """

    def __init__(self, config: ForgeStackConfig) -> None:
        """Initialize the Critic agent."""
        prompt_template = load_prompt("critic")
        super().__init__(
            config=config,
            agent_config=config.agents.critic,
            prompt_template=prompt_template,
        )

    @property
    def role(self) -> str:
        """Get the role name."""
        return "critic"

    def _build_user_message(self, context: AgentContext) -> str:
        """Build user message with critic-specific formatting."""
        parts = [
            f"## Task Type: {context.task_type}",
            f"\n## Original Task Description\n\n{context.task_description}",
        ]

        if context.codebase_summary:
            parts.append(f"## Codebase Context\n\n{context.codebase_summary}")

        # Include evaluation history for revision rounds
        if context.evaluation_history:
            parts.append(self._format_evaluation_history(context.evaluation_history))

        if context.previous_output:
            parts.append(
                f"## Proposal to Evaluate (Round {context.round_number})\n\n"
                f"{context.previous_output}"
            )
        else:
            parts.append("## Error\n\nNo proposal provided to evaluate.")

        # Different instructions for first round vs revision rounds
        if context.evaluation_history:
            parts.append(
                "\n**Instructions:** This is a REVISED proposal. Evaluate by:\n"
                "1. Reviewing your previous evaluation(s) above\n"
                "2. Checking whether the weaknesses you identified have been addressed\n"
                "3. Assessing any new strengths or issues\n"
                "4. Providing an updated score that reflects improvement (or lack thereof)\n\n"
                "**Scoring guidance:**\n"
                "- If major issues were fixed: Score should increase by 0.5-1.5 points\n"
                "- If minor issues were fixed: Score should increase by 0.2-0.5 points\n"
                "- If issues remain unaddressed: Explain which ones and keep score similar\n"
                "- If new issues were introduced: Score may decrease\n\n"
                "Provide:\n"
                "1. A score from 0.0 to 10.0 (format: `SCORE: X.X`)\n"
                "2. Which previous weaknesses were addressed (or not)\n"
                "3. Any new issues identified\n"
                "4. Specific recommendations for further improvement\n\n"
                "Be rigorous but constructive. The proposal needs a score >= 9.2 "
                "(0.92 normalized) to pass."
            )
        else:
            parts.append(
                "\n**Instructions:** Please evaluate this proposal thoroughly. "
                "Provide:\n"
                "1. A score from 0.0 to 10.0 (format: `SCORE: X.X`)\n"
                "2. Identified strengths\n"
                "3. Identified weaknesses\n"
                "4. Specific recommendations for improvement\n\n"
                "Be rigorous but constructive. The proposal needs a score >= 9.2 "
                "(0.92 normalized) to pass."
            )

        return "\n\n".join(parts)

    def _parse_score(self, content: str) -> float:
        """Extract the score from the critic's response.

        Looks for patterns like:
        - SCORE: 8.5
        - Score: 8.5/10
        - **Score:** 8.5
        """
        patterns = [
            r"SCORE:\s*(\d+\.?\d*)",
            r"Score:\s*(\d+\.?\d*)",
            r"\*\*Score\*\*:\s*(\d+\.?\d*)",
            r"score[:\s]+(\d+\.?\d*)\s*/?\s*10",
        ]

        for pattern in patterns:
            match = re.search(pattern, content, re.IGNORECASE)
            if match:
                score = float(match.group(1))
                # Normalize to 0-10 range if needed
                if score > 10:
                    score = 10.0
                return score

        # Default to a mid-range score if not found
        return 5.0

    def _parse_evaluation(self, content: str) -> CriticEvaluation:
        """Parse the full evaluation from the response."""
        score = self._parse_score(content)

        # Extract sections using common headers
        strengths = self._extract_list(content, ["strengths", "pros", "positives"])
        weaknesses = self._extract_list(content, ["weaknesses", "cons", "issues", "concerns"])
        recommendations = self._extract_list(
            content, ["recommendations", "suggestions", "improvements", "next steps"]
        )

        return CriticEvaluation(
            score=score,
            feedback=content,
            strengths=strengths,
            weaknesses=weaknesses,
            recommendations=recommendations,
        )

    def _extract_list(self, content: str, headers: list[str]) -> list[str]:
        """Extract a bulleted list from content under given headers."""
        items = []

        for header in headers:
            # Look for section starting with header
            pattern = rf"(?:^|\n)#+\s*{header}[:\s]*\n((?:[-*]\s+.+\n?)+)"
            match = re.search(pattern, content, re.IGNORECASE | re.MULTILINE)
            if match:
                list_content = match.group(1)
                # Extract individual items
                item_pattern = r"[-*]\s+(.+)"
                items.extend(re.findall(item_pattern, list_content))
                break

        return items

    def _format_evaluation_history(self, history: list[dict[str, Any]]) -> str:
        """Format evaluation history for the Critic's context.

        Args:
            history: List of previous evaluation records

        Returns:
            Formatted string with evaluation history
        """
        lines = ["## Your Previous Evaluations\n"]
        lines.append(
            "Below are your evaluations from previous rounds. "
            "Use these to assess whether the Generator addressed your concerns.\n"
        )

        for entry in history:
            round_num = entry["round"]
            score = entry["score"]
            weaknesses = entry.get("weaknesses", [])
            recommendations = entry.get("recommendations", [])
            proposal_hash = entry.get("proposal_hash", "unknown")

            lines.append(f"### Round {round_num} (Score: {score:.2f}, Hash: {proposal_hash})")

            if weaknesses:
                lines.append("\n**Weaknesses you identified:**")
                for w in weaknesses:
                    lines.append(f"- {w}")

            if recommendations:
                lines.append("\n**Recommendations you gave:**")
                for r in recommendations:
                    lines.append(f"- {r}")

            lines.append("")  # Blank line between rounds

        return "\n".join(lines)

    async def process(self, context: AgentContext) -> AgentResponse:
        """Process the context and evaluate the proposal.

        Args:
            context: The agent context with the proposal to evaluate

        Returns:
            AgentResponse containing the evaluation
        """
        response = await self.execute(context)

        # Parse the evaluation and attach structured data
        evaluation = self._parse_evaluation(response.content)

        # Add evaluation metadata to response
        response.evaluation = evaluation

        return response

    def get_normalized_score(self, response: AgentResponse) -> float:
        """Get the normalized score (0-1) from a response.

        Args:
            response: The critic's response

        Returns:
            Score normalized to 0-1 range
        """
        if response.evaluation is not None:
            return response.evaluation.score / 10.0
        return self._parse_score(response.content) / 10.0
