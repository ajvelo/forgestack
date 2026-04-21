"""Tests for ForgeStack orchestrator."""

from datetime import datetime
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from forgestack.agents.base import AgentContext, AgentResponse
from forgestack.config import (
    AgentConfig,
    AgentsConfig,
    CodebaseConfig,
    ForgeStackConfig,
    OrchestratorConfig,
    PersistenceConfig,
)
from forgestack.orchestrator.critique_round import CritiqueResult, CritiqueRound, RoundResult
from forgestack.orchestrator.engine import SessionResult


@pytest.fixture
def mock_config():
    """Create a mock configuration for testing."""
    return ForgeStackConfig(
        orchestrator=OrchestratorConfig(
            max_rounds=3,
            consensus_threshold=0.92,
        ),
        agents=AgentsConfig(
            generator=AgentConfig(
                model="claude-sonnet-4-5-20250929",
                temperature=0.7,
                max_tokens=4096,
            ),
            critic=AgentConfig(
                model="claude-sonnet-4-5-20250929",
                temperature=0.2,
                max_tokens=2048,
            ),
            synthesizer=AgentConfig(
                model="claude-sonnet-4-5-20250929",
                temperature=0.4,
                max_tokens=4096,
            ),
        ),
        codebase=CodebaseConfig(
            repos={
                "demo-app": "~/demo-app",
                "demo-library": "~/demo-library",
            }
        ),
        persistence=PersistenceConfig(
            database_path="./data/test.db",
        ),
    )


@pytest.fixture
def sample_context():
    """Create a sample agent context for testing."""
    return AgentContext(
        repo_key="demo-app",
        repo_path=Path("/tmp/test-repo"),
        task_type="feature",
        task_description="Add a new feature",
    )


class TestCritiqueRound:
    """Tests for the CritiqueRound class."""

    def test_critique_result_defaults(self):
        """Test CritiqueResult default values."""
        result = CritiqueResult()

        assert result.rounds == []
        assert result.final_proposal == ""
        assert result.final_score == 0.0
        assert result.passed_consensus is False

    def test_round_result_creation(self):
        """Test RoundResult creation."""
        generator_response = AgentResponse(content="Proposal", raw_response=None)
        critic_response = AgentResponse(content="SCORE: 9.5", raw_response=None)

        result = RoundResult(
            round_number=1,
            generator_response=generator_response,
            critic_response=critic_response,
            score=0.95,
            passed=True,
        )

        assert result.round_number == 1
        assert result.score == 0.95
        assert result.passed is True

    @pytest.mark.asyncio
    async def test_critique_round_consensus_reached(self, mock_config, sample_context):
        """Test critique round when consensus is reached on first try."""
        # Mock generator and critic
        mock_generator = AsyncMock()
        mock_generator.process = AsyncMock(
            return_value=AgentResponse(content="Great proposal", raw_response=None)
        )

        mock_critic = AsyncMock()
        mock_critic.process = AsyncMock(
            return_value=AgentResponse(content="SCORE: 9.5", raw_response=None)
        )
        mock_critic.get_normalized_score = MagicMock(return_value=0.95)

        # Create critique round with mocked console
        with patch("forgestack.orchestrator.critique_round.Console"):
            critique_round = CritiqueRound(
                config=mock_config,
                generator=mock_generator,
                critic=mock_critic,
            )

            result = await critique_round.run(sample_context)

        assert result.passed_consensus is True
        assert result.final_score == 0.95
        assert result.total_rounds == 1
        assert len(result.rounds) == 1

    @pytest.mark.asyncio
    async def test_critique_round_needs_revision(self, mock_config, sample_context):
        """Test critique round when revision is needed."""
        mock_generator = AsyncMock()
        mock_generator.process = AsyncMock(
            side_effect=[
                AgentResponse(content="First proposal", raw_response=None),
                AgentResponse(content="Revised proposal", raw_response=None),
            ]
        )

        mock_critic = AsyncMock()
        mock_critic.process = AsyncMock(
            side_effect=[
                AgentResponse(content="SCORE: 7.0", raw_response=None),
                AgentResponse(content="SCORE: 9.3", raw_response=None),
            ]
        )
        mock_critic.get_normalized_score = MagicMock(side_effect=[0.70, 0.93])

        with patch("forgestack.orchestrator.critique_round.Console"):
            critique_round = CritiqueRound(
                config=mock_config,
                generator=mock_generator,
                critic=mock_critic,
            )

            result = await critique_round.run(sample_context)

        assert result.passed_consensus is True
        assert result.total_rounds == 2
        assert len(result.rounds) == 2

    @pytest.mark.asyncio
    async def test_critique_round_max_rounds_reached(self, mock_config, sample_context):
        """Test critique round when max rounds is reached without consensus."""
        mock_generator = AsyncMock()
        mock_generator.process = AsyncMock(
            return_value=AgentResponse(content="Proposal", raw_response=None)
        )

        mock_critic = AsyncMock()
        mock_critic.process = AsyncMock(
            return_value=AgentResponse(content="SCORE: 8.0", raw_response=None)
        )
        mock_critic.get_normalized_score = MagicMock(return_value=0.80)

        with patch("forgestack.orchestrator.critique_round.Console"):
            critique_round = CritiqueRound(
                config=mock_config,
                generator=mock_generator,
                critic=mock_critic,
            )

            result = await critique_round.run(sample_context)

        assert result.passed_consensus is False
        assert result.total_rounds == mock_config.orchestrator.max_rounds


class TestSessionResult:
    """Tests for SessionResult."""

    def test_session_result_creation(self):
        """Test creating a session result."""
        result = SessionResult(
            session_id="test-123",
            repo_key="demo-app",
            task_type="feature",
            task_description="Add feature",
            final_output="Implementation details",
            final_score=0.95,
            rounds_count=2,
            passed_consensus=True,
            created_at=datetime.now(),
        )

        assert result.session_id == "test-123"
        assert result.repo_key == "demo-app"
        assert result.final_score == 0.95
        assert result.passed_consensus is True


class TestOrchestratorConfig:
    """Tests for orchestrator configuration."""

    def test_consensus_threshold_default(self, mock_config):
        """Test that consensus threshold is set correctly."""
        assert mock_config.orchestrator.consensus_threshold == 0.92

    def test_max_rounds_default(self, mock_config):
        """Test that max rounds is set correctly."""
        assert mock_config.orchestrator.max_rounds == 3
