"""Tests for ForgeStack agents."""

import pytest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

from forgestack.agents.base import AgentContext, AgentResponse
from forgestack.agents.generator import GeneratorAgent
from forgestack.agents.critic import CriticAgent, CriticEvaluation
from forgestack.agents.synthesizer import SynthesizerAgent
from forgestack.config import ForgeStackConfig, AgentConfig, AgentsConfig


@pytest.fixture
def mock_config():
    """Create a mock configuration for testing."""
    return ForgeStackConfig(
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
        )
    )


@pytest.fixture
def sample_context():
    """Create a sample agent context for testing."""
    return AgentContext(
        repo_key="app",
        repo_path=Path("/tmp/test-repo"),
        task_type="feature",
        task_description="Add a new button to the home screen",
        codebase_summary="Flutter app with standard structure",
    )


class TestAgentContext:
    """Tests for AgentContext."""

    def test_context_creation(self, sample_context):
        """Test creating an agent context."""
        assert sample_context.repo_key == "app"
        assert sample_context.task_type == "feature"
        assert sample_context.round_number == 1

    def test_context_with_feedback(self, sample_context):
        """Test context with previous output and feedback."""
        sample_context.previous_output = "Previous proposal"
        sample_context.feedback = "Needs improvement"
        sample_context.round_number = 2

        assert sample_context.previous_output == "Previous proposal"
        assert sample_context.feedback == "Needs improvement"
        assert sample_context.round_number == 2


class TestCriticAgent:
    """Tests for the Critic agent."""

    def test_parse_score_standard_format(self):
        """Test parsing score from standard format."""
        content = "This is a review.\n\nSCORE: 8.5\n\nMore content."

        with patch.object(CriticAgent, '__init__', lambda x, y: None):
            critic = CriticAgent.__new__(CriticAgent)
            score = critic._parse_score(content)

        assert score == 8.5

    def test_parse_score_with_denominator(self):
        """Test parsing score with /10 format."""
        content = "Review content.\n\nScore: 9.2/10\n\nConclusion."

        with patch.object(CriticAgent, '__init__', lambda x, y: None):
            critic = CriticAgent.__new__(CriticAgent)
            score = critic._parse_score(content)

        assert score == 9.2

    def test_parse_score_bold_format(self):
        """Test parsing score from bold markdown format."""
        content = "Analysis\n\n**Score**: 7.8\n\nDetails"

        with patch.object(CriticAgent, '__init__', lambda x, y: None):
            critic = CriticAgent.__new__(CriticAgent)
            score = critic._parse_score(content)

        assert score == 7.8

    def test_parse_score_default_when_missing(self):
        """Test default score when no score found."""
        content = "Review without any score mentioned."

        with patch.object(CriticAgent, '__init__', lambda x, y: None):
            critic = CriticAgent.__new__(CriticAgent)
            score = critic._parse_score(content)

        assert score == 5.0  # Default mid-range score

    def test_normalized_score(self):
        """Test normalized score calculation."""
        response = AgentResponse(content="SCORE: 9.2", raw_response=None)

        with patch.object(CriticAgent, '__init__', lambda x, y: None):
            critic = CriticAgent.__new__(CriticAgent)
            normalized = critic.get_normalized_score(response)

        assert normalized == pytest.approx(0.92)


class TestAgentResponse:
    """Tests for AgentResponse."""

    def test_response_creation(self):
        """Test creating an agent response."""
        response = AgentResponse(
            content="Test response content",
            raw_response={"id": "test"},
            usage={"input_tokens": 100, "output_tokens": 200},
        )

        assert response.content == "Test response content"
        assert response.usage["input_tokens"] == 100
        assert response.usage["output_tokens"] == 200


class TestGeneratorAgent:
    """Tests for the Generator agent."""

    @pytest.mark.asyncio
    async def test_generator_builds_user_message(self, mock_config, sample_context):
        """Test that Generator builds correct user message."""
        with patch.object(GeneratorAgent, '__init__', lambda x, y: None):
            generator = GeneratorAgent.__new__(GeneratorAgent)
            generator.config = mock_config
            generator.agent_config = mock_config.agents.generator
            generator.prompt_template = "Test prompt"

            message = generator._build_user_message(sample_context)

        assert "feature" in message
        assert "Add a new button" in message
        assert "Instructions" in message

    @pytest.mark.asyncio
    async def test_generator_revision_message(self, mock_config, sample_context):
        """Test Generator message includes feedback for revisions."""
        sample_context.previous_output = "Original proposal"
        sample_context.feedback = "Add error handling"
        sample_context.round_number = 2

        with patch.object(GeneratorAgent, '__init__', lambda x, y: None):
            generator = GeneratorAgent.__new__(GeneratorAgent)
            generator.config = mock_config
            generator.agent_config = mock_config.agents.generator
            generator.prompt_template = "Test prompt"

            message = generator._build_user_message(sample_context)

        assert "Previous Proposal" in message
        assert "Critic Feedback" in message
        assert "Add error handling" in message


class TestSynthesizerAgent:
    """Tests for the Synthesizer agent."""

    @pytest.mark.asyncio
    async def test_synthesizer_builds_user_message(self, mock_config, sample_context):
        """Test that Synthesizer builds correct user message."""
        sample_context.previous_output = "Final proposal"
        sample_context.feedback = "Approved with minor notes"

        with patch.object(SynthesizerAgent, '__init__', lambda x, y: None):
            synthesizer = SynthesizerAgent.__new__(SynthesizerAgent)
            synthesizer.config = mock_config
            synthesizer.agent_config = mock_config.agents.synthesizer
            synthesizer.prompt_template = "Test prompt"

            message = synthesizer._build_user_message(sample_context)

        assert "Final Generator Proposal" in message
        assert "Critic Evaluation" in message
        assert "Implementation Steps" in message
