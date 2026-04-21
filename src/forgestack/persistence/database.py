"""SQLite database operations for ForgeStack."""

from datetime import datetime
from pathlib import Path

import aiosqlite

from forgestack.persistence.models import AgentResponseRecord, SessionRecord


class SessionDatabase:
    """SQLite database for session persistence."""

    def __init__(self, db_path: Path) -> None:
        """Initialize the database.

        Args:
            db_path: Path to the SQLite database file
        """
        self.db_path = db_path
        self._initialized = False

    async def _ensure_initialized(self) -> None:
        """Ensure the database schema is created."""
        if self._initialized:
            return

        # Create directory if needed
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        async with aiosqlite.connect(self.db_path) as db:
            # Create sessions table
            await db.execute("""
                CREATE TABLE IF NOT EXISTS sessions (
                    id TEXT PRIMARY KEY,
                    repo_key TEXT NOT NULL,
                    task_type TEXT NOT NULL,
                    task_description TEXT NOT NULL,
                    final_output TEXT NOT NULL,
                    final_score REAL NOT NULL,
                    rounds_count INTEGER NOT NULL,
                    created_at TEXT NOT NULL
                )
            """)

            # Create agent_responses table
            await db.execute("""
                CREATE TABLE IF NOT EXISTS agent_responses (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL,
                    agent_type TEXT NOT NULL,
                    round_number INTEGER NOT NULL,
                    content TEXT NOT NULL,
                    score REAL,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY (session_id) REFERENCES sessions(id)
                )
            """)

            # Create indexes
            await db.execute("""
                CREATE INDEX IF NOT EXISTS idx_sessions_repo_key
                ON sessions(repo_key)
            """)
            await db.execute("""
                CREATE INDEX IF NOT EXISTS idx_sessions_created_at
                ON sessions(created_at DESC)
            """)
            await db.execute("""
                CREATE INDEX IF NOT EXISTS idx_agent_responses_session_id
                ON agent_responses(session_id)
            """)

            await db.commit()

        self._initialized = True

    async def save_session(self, session: SessionRecord) -> None:
        """Save a session and its agent responses.

        Args:
            session: The session record to save
        """
        await self._ensure_initialized()

        async with aiosqlite.connect(self.db_path) as db:
            # Insert session
            await db.execute(
                """
                INSERT INTO sessions
                (id, repo_key, task_type, task_description, final_output,
                 final_score, rounds_count, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    session.id,
                    session.repo_key,
                    session.task_type,
                    session.task_description,
                    session.final_output,
                    session.final_score,
                    session.rounds_count,
                    session.created_at.isoformat(),
                ),
            )

            # Insert agent responses
            for response in session.agent_responses:
                await db.execute(
                    """
                    INSERT INTO agent_responses
                    (session_id, agent_type, round_number, content, score, created_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        response.session_id,
                        response.agent_type,
                        response.round_number,
                        response.content,
                        response.score,
                        response.created_at.isoformat(),
                    ),
                )

            await db.commit()

    async def get_session(self, session_id: str) -> SessionRecord | None:
        """Get a session by ID.

        Args:
            session_id: The session ID

        Returns:
            SessionRecord or None if not found
        """
        await self._ensure_initialized()

        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row

            # Get session
            cursor = await db.execute(
                "SELECT * FROM sessions WHERE id = ?",
                (session_id,),
            )
            row = await cursor.fetchone()

            if not row:
                return None

            # Get agent responses
            cursor = await db.execute(
                """
                SELECT * FROM agent_responses
                WHERE session_id = ?
                ORDER BY round_number, agent_type
                """,
                (session_id,),
            )
            response_rows = await cursor.fetchall()

            agent_responses = [
                AgentResponseRecord(
                    session_id=r["session_id"],
                    agent_type=r["agent_type"],
                    round_number=r["round_number"],
                    content=r["content"],
                    score=r["score"],
                    created_at=datetime.fromisoformat(r["created_at"]),
                )
                for r in response_rows
            ]

            return SessionRecord(
                id=row["id"],
                repo_key=row["repo_key"],
                task_type=row["task_type"],
                task_description=row["task_description"],
                final_output=row["final_output"],
                final_score=row["final_score"],
                rounds_count=row["rounds_count"],
                created_at=datetime.fromisoformat(row["created_at"]),
                agent_responses=agent_responses,
            )

    async def get_sessions(
        self,
        limit: int = 10,
        repo_filter: str | None = None,
    ) -> list[SessionRecord]:
        """Get recent sessions.

        Args:
            limit: Maximum number of sessions to return
            repo_filter: Optional repository key to filter by

        Returns:
            List of SessionRecord objects
        """
        await self._ensure_initialized()

        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row

            if repo_filter:
                cursor = await db.execute(
                    """
                    SELECT * FROM sessions
                    WHERE repo_key = ?
                    ORDER BY created_at DESC
                    LIMIT ?
                    """,
                    (repo_filter, limit),
                )
            else:
                cursor = await db.execute(
                    """
                    SELECT * FROM sessions
                    ORDER BY created_at DESC
                    LIMIT ?
                    """,
                    (limit,),
                )

            rows = await cursor.fetchall()

            sessions = []
            for row in rows:
                sessions.append(
                    SessionRecord(
                        id=row["id"],
                        repo_key=row["repo_key"],
                        task_type=row["task_type"],
                        task_description=row["task_description"],
                        final_output=row["final_output"],
                        final_score=row["final_score"],
                        rounds_count=row["rounds_count"],
                        created_at=datetime.fromisoformat(row["created_at"]),
                        agent_responses=[],  # Not loaded for list view
                    )
                )

            return sessions

    async def delete_session(self, session_id: str) -> bool:
        """Delete a session and its responses.

        Args:
            session_id: The session ID to delete

        Returns:
            True if deleted, False if not found
        """
        await self._ensure_initialized()

        async with aiosqlite.connect(self.db_path) as db:
            # Delete responses first
            await db.execute(
                "DELETE FROM agent_responses WHERE session_id = ?",
                (session_id,),
            )

            # Delete session
            cursor = await db.execute(
                "DELETE FROM sessions WHERE id = ?",
                (session_id,),
            )

            await db.commit()
            return cursor.rowcount > 0
