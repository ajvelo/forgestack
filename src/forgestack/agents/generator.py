"""Generator agent - proposes solutions for tasks."""

from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import TYPE_CHECKING, Any

from forgestack.agents.base import AgentContext, AgentResponse, BaseAgent
from forgestack.config import ForgeStackConfig
from forgestack.prompts import load_prompt

if TYPE_CHECKING:
    from forgestack.mcp.client import MCPClient

logger = logging.getLogger(__name__)


class GeneratorAgent(BaseAgent):
    """Generator agent that proposes solutions.

    The Generator is responsible for:
    - Producing 1-2 solution approaches for given tasks
    - Code improvements and refactors
    - New feature implementation
    - Bug fixes
    - Architecture patterns and design proposals
    - Aligning proposals with existing codebase patterns
    - Consulting the configured design system repo (if any) for UI work
    - Reading relevant code files via MCP tools
    """

    # Class-level defaults so the instance is usable even if a caller
    # constructs it without going through __init__ (e.g. in tests via
    # __new__). These are always overwritten in __init__.
    mcp_client: MCPClient | None = None
    _code_context: str = ""

    def __init__(
        self,
        config: ForgeStackConfig,
        mcp_client: MCPClient | None = None,
    ) -> None:
        """Initialize the Generator agent.

        Args:
            config: ForgeStack configuration
            mcp_client: Optional MCP client for reading code files
        """
        prompt_template = load_prompt("generator")
        super().__init__(
            config=config,
            agent_config=config.agents.generator,
            prompt_template=prompt_template,
        )
        self.mcp_client = mcp_client
        self._code_context = ""

    @property
    def role(self) -> str:
        """Get the role name."""
        return "generator"

    def _format_evaluation_history(self, history: list[dict[str, Any]]) -> str:
        """Format evaluation history to help Generator understand progress.

        Args:
            history: List of evaluation entries from previous rounds

        Returns:
            Formatted string showing score progression and key issues
        """
        if not history:
            return ""

        lines = ["## Score History\n"]
        for entry in history:
            score = entry.get("score", 0)
            round_num = entry.get("round", 0)
            lines.append(f"**Round {round_num}**: {score:.2f}/10")

            weaknesses = entry.get("weaknesses", [])
            if weaknesses:
                lines.append("Key issues:")
                for w in weaknesses[:3]:  # Limit to top 3
                    lines.append(f"  - {w}")
            lines.append("")

        return "\n".join(lines)

    def _identify_relevant_files(self, context: AgentContext) -> list[str]:
        """Identify files relevant to the task based on keywords.

        Args:
            context: Agent context containing task info and codebase summary

        Returns:
            List of file paths that might be relevant
        """
        relevant_files: list[str] = []

        if not context.codebase_summary or not context.repo_path:
            return relevant_files

        # Extract keywords from task description
        task_lower = context.task_description.lower()

        # Common Flutter file patterns to look for
        patterns = []

        # Feature-based keywords
        if "screen" in task_lower or "page" in task_lower:
            patterns.extend(["screens/", "pages/", "_screen.dart", "_page.dart"])
        if "widget" in task_lower or "component" in task_lower:
            patterns.extend(["widgets/", "components/", "_widget.dart"])
        if "model" in task_lower or "data" in task_lower:
            patterns.extend(["models/", "data/", "_model.dart"])
        if "service" in task_lower or "api" in task_lower:
            patterns.extend(["services/", "api/", "_service.dart"])
        if "bloc" in task_lower or "cubit" in task_lower or "state" in task_lower:
            patterns.extend(["bloc/", "cubit/", "_bloc.dart", "_cubit.dart"])

        # Extract specific file mentions from task
        file_mentions = re.findall(r"[\w_/]+\.dart", task_lower)
        patterns.extend(file_mentions)

        # Parse codebase summary for actual file paths
        summary_lines = context.codebase_summary.split("\n")
        for line in summary_lines:
            # Look for .dart files in the summary
            dart_files = re.findall(r"([\w_/]+\.dart)", line)
            for dart_file in dart_files:
                for pattern in patterns:
                    if pattern in dart_file.lower():
                        # Construct full path
                        full_path = str(context.repo_path / "lib" / dart_file)
                        if full_path not in relevant_files:
                            relevant_files.append(full_path)

        # Also check for main entry points
        main_files = [
            str(context.repo_path / "lib" / "main.dart"),
            str(context.repo_path / "lib" / "app.dart"),
        ]
        for main_file in main_files:
            if Path(main_file).exists() and main_file not in relevant_files:
                relevant_files.append(main_file)

        return relevant_files[:5]  # Limit to 5 files

    async def _read_relevant_files(self, context: AgentContext) -> str:
        """Read key files to understand existing patterns.

        Args:
            context: Agent context with repo path and task info

        Returns:
            Formatted string with code file contents
        """
        if not self.mcp_client:
            return ""

        files_to_read = self._identify_relevant_files(context)
        if not files_to_read:
            return ""

        contents: list[str] = []
        for file_path in files_to_read[:3]:  # Read up to 3 files
            try:
                result = await self.mcp_client.invoke_tool("file_read", {"path": file_path})
                if result.get("status") == "success":
                    content = result.get("content", "")
                    # Truncate very long files
                    if len(content) > 2000:
                        content = content[:2000] + "\n... (truncated)"
                    file_name = Path(file_path).name
                    contents.append(f"### {file_name}\n```dart\n{content}\n```")
                    logger.debug(f"Read file for context: {file_path}")
            except Exception as e:
                logger.debug(f"Failed to read file {file_path}: {e}")

        if contents:
            return "## Relevant Code Files\n\n" + "\n\n".join(contents)
        return ""

    def _build_user_message(self, context: AgentContext) -> str:
        """Build user message with generator-specific formatting.

        Args:
            context: Agent context with task info

        Returns:
            Formatted user message
        """
        parts = [
            f"## Task Type: {context.task_type}",
            f"\n## Task Description\n\n{context.task_description}",
        ]

        if context.codebase_summary:
            parts.append(f"## Codebase Context\n\n{context.codebase_summary}")

        # Include actual code files if available (set by process())
        if self._code_context:
            parts.append(self._code_context)

        if context.design_system_summary:
            parts.append(f"## Design System Reference\n\n{context.design_system_summary}")

        if context.previous_output and context.feedback:
            # Include evaluation history if available
            if context.evaluation_history:
                parts.append(self._format_evaluation_history(context.evaluation_history))

            parts.append(
                f"## Previous Proposal (Round {context.round_number - 1})\n\n"
                f"{context.previous_output}"
            )
            parts.append(f"## Critic Feedback to Address\n\n{context.feedback}")
            parts.append(
                "\n**Instructions:** Please revise your proposal based on the "
                "feedback above. Address each point raised by the Critic. "
                "Focus on the key issues from the score history to improve your score."
            )
        else:
            parts.append(
                "\n**Instructions:** Please provide 1-2 solution approaches for "
                "this task. Include code snippets where appropriate and explain "
                "your reasoning and trade-offs."
            )

        return "\n\n".join(parts)

    async def process(self, context: AgentContext) -> AgentResponse:
        """Process the context and generate solution proposals.

        Args:
            context: The agent context with task information

        Returns:
            AgentResponse containing the proposed solutions
        """
        # Gather code context via MCP on first round only (to avoid redundant reads)
        if context.round_number == 1 and self.mcp_client:
            logger.debug("Gathering code context for Generator...")
            self._code_context = await self._read_relevant_files(context)
            if self._code_context:
                logger.info("Loaded code context for Generator")

        return await self.execute(context)
