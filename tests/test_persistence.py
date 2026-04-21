"""Tests for ForgeStack persistence layer."""

import pytest
import tempfile
from pathlib import Path
from datetime import datetime

from forgestack.persistence.database import SessionDatabase
from forgestack.persistence.models import SessionRecord, AgentResponseRecord


@pytest.fixture
def temp_db_path():
    """Create a temporary database path for testing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir) / "test.db"


@pytest.fixture
def sample_session():
    """Create a sample session record for testing."""
    return SessionRecord(
        id="test-session-123",
        repo_key="app",
        task_type="feature",
        task_description="Add a new feature to the app",
        final_output="Implementation completed successfully",
        final_score=0.95,
        rounds_count=2,
        created_at=datetime.now(),
        agent_responses=[
            AgentResponseRecord(
                session_id="test-session-123",
                agent_type="generator",
                round_number=1,
                content="First proposal",
            ),
            AgentResponseRecord(
                session_id="test-session-123",
                agent_type="critic",
                round_number=1,
                content="SCORE: 8.0",
                score=0.80,
            ),
            AgentResponseRecord(
                session_id="test-session-123",
                agent_type="generator",
                round_number=2,
                content="Revised proposal",
            ),
            AgentResponseRecord(
                session_id="test-session-123",
                agent_type="critic",
                round_number=2,
                content="SCORE: 9.5",
                score=0.95,
            ),
        ],
    )


class TestSessionRecord:
    """Tests for SessionRecord model."""

    def test_session_record_creation(self, sample_session):
        """Test creating a session record."""
        assert sample_session.id == "test-session-123"
        assert sample_session.repo_key == "app"
        assert sample_session.task_type == "feature"
        assert sample_session.final_score == 0.95
        assert len(sample_session.agent_responses) == 4

    def test_session_record_defaults(self):
        """Test session record default values."""
        session = SessionRecord(
            id="test",
            repo_key="app",
            task_type="bugfix",
            task_description="Fix bug",
            final_output="Fixed",
            final_score=0.9,
            rounds_count=1,
        )

        assert session.agent_responses == []
        assert isinstance(session.created_at, datetime)


class TestAgentResponseRecord:
    """Tests for AgentResponseRecord model."""

    def test_agent_response_creation(self):
        """Test creating an agent response record."""
        response = AgentResponseRecord(
            session_id="test-123",
            agent_type="generator",
            round_number=1,
            content="Test content",
        )

        assert response.session_id == "test-123"
        assert response.agent_type == "generator"
        assert response.score is None

    def test_agent_response_with_score(self):
        """Test agent response with score."""
        response = AgentResponseRecord(
            session_id="test-123",
            agent_type="critic",
            round_number=1,
            content="SCORE: 9.0",
            score=0.90,
        )

        assert response.score == 0.90


class TestSessionDatabase:
    """Tests for SessionDatabase."""

    @pytest.mark.asyncio
    async def test_database_initialization(self, temp_db_path):
        """Test database initialization creates tables."""
        db = SessionDatabase(temp_db_path)
        await db._ensure_initialized()

        assert temp_db_path.exists()

    @pytest.mark.asyncio
    async def test_save_and_retrieve_session(self, temp_db_path, sample_session):
        """Test saving and retrieving a session."""
        db = SessionDatabase(temp_db_path)

        # Save session
        await db.save_session(sample_session)

        # Retrieve session
        retrieved = await db.get_session(sample_session.id)

        assert retrieved is not None
        assert retrieved.id == sample_session.id
        assert retrieved.repo_key == sample_session.repo_key
        assert retrieved.final_score == sample_session.final_score
        assert len(retrieved.agent_responses) == len(sample_session.agent_responses)

    @pytest.mark.asyncio
    async def test_get_nonexistent_session(self, temp_db_path):
        """Test getting a session that doesn't exist."""
        db = SessionDatabase(temp_db_path)

        result = await db.get_session("nonexistent-id")

        assert result is None

    @pytest.mark.asyncio
    async def test_get_sessions_list(self, temp_db_path, sample_session):
        """Test getting list of sessions."""
        db = SessionDatabase(temp_db_path)

        # Save multiple sessions
        for i in range(3):
            session = SessionRecord(
                id=f"session-{i}",
                repo_key="app" if i < 2 else "portal",
                task_type="feature",
                task_description=f"Task {i}",
                final_output=f"Output {i}",
                final_score=0.9 + i * 0.01,
                rounds_count=1,
            )
            await db.save_session(session)

        # Get all sessions
        sessions = await db.get_sessions(limit=10)
        assert len(sessions) == 3

        # Get sessions filtered by repo
        app_sessions = await db.get_sessions(limit=10, repo_filter="app")
        assert len(app_sessions) == 2

    @pytest.mark.asyncio
    async def test_delete_session(self, temp_db_path, sample_session):
        """Test deleting a session."""
        db = SessionDatabase(temp_db_path)

        # Save and delete
        await db.save_session(sample_session)
        deleted = await db.delete_session(sample_session.id)

        assert deleted is True

        # Verify deletion
        retrieved = await db.get_session(sample_session.id)
        assert retrieved is None

    @pytest.mark.asyncio
    async def test_delete_nonexistent_session(self, temp_db_path):
        """Test deleting a session that doesn't exist."""
        db = SessionDatabase(temp_db_path)

        deleted = await db.delete_session("nonexistent")

        assert deleted is False


class TestDatabaseIntegrity:
    """Tests for database integrity and edge cases."""

    @pytest.mark.asyncio
    async def test_multiple_sessions_same_repo(self, temp_db_path):
        """Test storing multiple sessions for the same repository."""
        db = SessionDatabase(temp_db_path)

        for i in range(5):
            session = SessionRecord(
                id=f"session-{i}",
                repo_key="app",
                task_type="feature",
                task_description=f"Feature {i}",
                final_output=f"Output {i}",
                final_score=0.9,
                rounds_count=1,
            )
            await db.save_session(session)

        sessions = await db.get_sessions(limit=10, repo_filter="app")
        assert len(sessions) == 5

    @pytest.mark.asyncio
    async def test_session_with_long_content(self, temp_db_path):
        """Test storing session with long content."""
        db = SessionDatabase(temp_db_path)

        long_content = "x" * 100000  # 100KB of content

        session = SessionRecord(
            id="long-content-session",
            repo_key="app",
            task_type="feature",
            task_description="Test long content",
            final_output=long_content,
            final_score=0.9,
            rounds_count=1,
            agent_responses=[
                AgentResponseRecord(
                    session_id="long-content-session",
                    agent_type="generator",
                    round_number=1,
                    content=long_content,
                ),
            ],
        )

        await db.save_session(session)
        retrieved = await db.get_session("long-content-session")

        assert retrieved is not None
        assert len(retrieved.final_output) == 100000
