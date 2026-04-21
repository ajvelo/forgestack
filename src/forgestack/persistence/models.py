"""Data models for ForgeStack persistence."""

from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class AgentResponseRecord:
    """Record of an agent's response."""

    session_id: str
    agent_type: str  # "generator", "critic", "synthesizer"
    round_number: int
    content: str
    score: float | None = None
    created_at: datetime = field(default_factory=datetime.now)


@dataclass
class SessionRecord:
    """Record of a ForgeStack session."""

    id: str
    repo_key: str
    task_type: str
    task_description: str
    final_output: str
    final_score: float
    rounds_count: int
    created_at: datetime = field(default_factory=datetime.now)
    agent_responses: list[AgentResponseRecord] = field(default_factory=list)
