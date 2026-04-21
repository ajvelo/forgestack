"""Base agent class for ForgeStack agents."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from anthropic import AsyncAnthropic

from forgestack.config import AgentConfig, ForgeStackConfig


@dataclass
class AgentContext:
    """Context provided to agents for task execution."""

    repo_key: str
    repo_path: Path
    task_type: str
    task_description: str
    codebase_summary: str | None = None
    design_system_summary: str | None = None
    mcp_tools: list[dict[str, Any]] | None = None
    previous_output: str | None = None
    feedback: str | None = None
    round_number: int = 1
    # Evaluation history for Critic to track improvements across rounds
    evaluation_history: list[dict[str, Any]] | None = None


@dataclass
class AgentResponse:
    """Response from an agent."""

    content: str
    raw_response: Any
    usage: dict[str, int] | None = None
    evaluation: Any | None = None  # For CriticEvaluation attachment


class BaseAgent(ABC):
    """Base class for all ForgeStack agents."""

    def __init__(
        self,
        config: ForgeStackConfig,
        agent_config: AgentConfig,
        prompt_template: str,
    ) -> None:
        """Initialize the agent.

        Args:
            config: Global ForgeStack configuration
            agent_config: Agent-specific configuration
            prompt_template: System prompt template for this agent
        """
        self.config = config
        self.agent_config = agent_config
        self.prompt_template = prompt_template

        # Initialize async Anthropic client
        api_key = config.anthropic.get_api_key()
        self.client = AsyncAnthropic(api_key=api_key)

    @property
    @abstractmethod
    def role(self) -> str:
        """Get the role name for this agent."""
        ...

    def _build_system_prompt(self, context: AgentContext) -> str:
        """Build the system prompt with context."""
        prompt = self.prompt_template

        # Replace placeholders in the prompt template
        replacements = {
            "{{REPO_KEY}}": context.repo_key,
            "{{REPO_PATH}}": str(context.repo_path),
            "{{TASK_TYPE}}": context.task_type,
            "{{TASK_DESCRIPTION}}": context.task_description,
            "{{CODEBASE_SUMMARY}}": context.codebase_summary or "Not available",
            "{{DESIGN_SYSTEM_SUMMARY}}": context.design_system_summary or "Not available",
            "{{ROUND_NUMBER}}": str(context.round_number),
        }

        for placeholder, value in replacements.items():
            prompt = prompt.replace(placeholder, value)

        return prompt

    def _build_user_message(self, context: AgentContext) -> str:
        """Build the user message based on context."""
        parts = [f"## Task\n\n{context.task_description}"]

        if context.previous_output:
            parts.append(f"## Previous Output\n\n{context.previous_output}")

        if context.feedback:
            parts.append(f"## Feedback to Address\n\n{context.feedback}")

        return "\n\n".join(parts)

    async def execute(self, context: AgentContext) -> AgentResponse:
        """Execute the agent with the given context.

        Args:
            context: The agent context containing task information

        Returns:
            AgentResponse with the agent's output
        """
        system_prompt = self._build_system_prompt(context)
        user_message = self._build_user_message(context)

        # Call the Anthropic API (async)
        response = await self.client.messages.create(
            model=self.agent_config.model,
            max_tokens=self.agent_config.max_tokens,
            temperature=self.agent_config.temperature,
            system=system_prompt,
            messages=[
                {"role": "user", "content": user_message}
            ],
        )

        # Extract content
        content = ""
        for block in response.content:
            if hasattr(block, "text"):
                content += block.text

        # Build usage info
        usage = None
        if response.usage:
            usage = {
                "input_tokens": response.usage.input_tokens,
                "output_tokens": response.usage.output_tokens,
            }

        return AgentResponse(
            content=content,
            raw_response=response,
            usage=usage,
        )

    @abstractmethod
    async def process(self, context: AgentContext) -> AgentResponse:
        """Process the context and return a response.

        This method should be implemented by subclasses to add
        any role-specific processing.
        """
        ...
