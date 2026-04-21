"""Synthesizer agent - merges proposals and feedback into final output."""

from forgestack.agents.base import AgentContext, AgentResponse, BaseAgent
from forgestack.config import ForgeStackConfig
from forgestack.prompts import load_prompt


class SynthesizerAgent(BaseAgent):
    """Synthesizer agent that produces final merged output.

    The Synthesizer is responsible for:
    - Taking the final Generator output and Critic feedback
    - Producing the final merged proposal
    - Generating ready-to-use code snippets or patches
    - Providing implementation steps with file paths
    - Creating a concise summary of recommended changes
    - Ensuring the result is implementable and consistent with repo conventions
    """

    def __init__(self, config: ForgeStackConfig) -> None:
        """Initialize the Synthesizer agent."""
        prompt_template = load_prompt("synthesizer")
        super().__init__(
            config=config,
            agent_config=config.agents.synthesizer,
            prompt_template=prompt_template,
        )

    @property
    def role(self) -> str:
        """Get the role name."""
        return "synthesizer"

    def _build_user_message(self, context: AgentContext) -> str:
        """Build user message with synthesizer-specific formatting."""
        parts = [
            f"## Task Type: {context.task_type}",
            f"\n## Original Task Description\n\n{context.task_description}",
        ]

        if context.codebase_summary:
            parts.append(f"## Codebase Context\n\n{context.codebase_summary}")

        if context.design_system_summary:
            parts.append(f"## Design System Reference\n\n{context.design_system_summary}")

        if context.previous_output:
            parts.append(
                f"## Final Generator Proposal\n\n{context.previous_output}"
            )

        if context.feedback:
            parts.append(
                f"## Critic Evaluation & Feedback\n\n{context.feedback}"
            )

        parts.append(
            "\n**Instructions:** Please synthesize the above into a final, "
            "actionable result. Provide:\n\n"
            "1. **Summary**: A brief description of the recommended changes\n"
            "2. **Implementation Steps**: Numbered steps with specific file paths\n"
            "3. **Code Changes**: Complete code snippets ready for implementation\n"
            "4. **Testing Recommendations**: How to verify the changes work\n"
            "5. **Potential Risks**: Any risks or considerations to be aware of\n\n"
            "Ensure all code is complete and can be directly copied into the codebase."
        )

        return "\n\n".join(parts)

    async def process(self, context: AgentContext) -> AgentResponse:
        """Process the context and synthesize the final output.

        Args:
            context: The agent context with proposal and feedback

        Returns:
            AgentResponse containing the synthesized final output
        """
        return await self.execute(context)
