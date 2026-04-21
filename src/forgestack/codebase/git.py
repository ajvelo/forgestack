"""Git utilities for codebase analysis."""

import logging
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from git import GitCommandError, InvalidGitRepositoryError, Repo

logger = logging.getLogger(__name__)


def _first_line_of_message(message: str | bytes) -> str:
    """GitPython can return commit messages as bytes on some configs;
    normalise to the first line of a string."""
    if isinstance(message, bytes):
        message = message.decode("utf-8", errors="replace")
    return message.strip().split("\n")[0]


@dataclass
class CommitInfo:
    """Information about a git commit."""

    sha: str
    message: str
    author: str
    date: datetime


@dataclass
class GitStatus:
    """Current git status information."""

    branch: str
    is_dirty: bool
    modified_files: list[str]
    untracked_files: list[str]
    staged_files: list[str]


class GitContext:
    """Provides git context for a repository."""

    def __init__(self, repo_path: Path) -> None:
        """Initialize git context.

        Args:
            repo_path: Path to the git repository
        """
        self.repo_path = repo_path
        self._repo: Repo | None = None

    def _get_repo(self) -> Repo | None:
        """Get or create the git.Repo instance."""
        if self._repo is None:
            try:
                self._repo = Repo(self.repo_path)
            except InvalidGitRepositoryError:
                return None
        return self._repo

    def is_git_repo(self) -> bool:
        """Check if the path is a git repository."""
        return self._get_repo() is not None

    def get_status(self) -> GitStatus | None:
        """Get current git status.

        Returns:
            GitStatus object or None if not a git repo
        """
        repo = self._get_repo()
        if not repo:
            return None

        try:
            # Get current branch
            branch = repo.active_branch.name
        except TypeError:
            # Detached HEAD state
            branch = f"detached@{repo.head.commit.hexsha[:7]}"

        # Get modified files (a_path can be None for some diff entries)
        modified = [p for item in repo.index.diff(None) if (p := item.a_path) is not None]

        # Get staged files
        staged = [p for item in repo.index.diff("HEAD") if (p := item.a_path) is not None]

        # Get untracked files
        untracked = repo.untracked_files

        return GitStatus(
            branch=branch,
            is_dirty=repo.is_dirty(),
            modified_files=modified,
            untracked_files=untracked,
            staged_files=staged,
        )

    def get_recent_commits(self, count: int = 5) -> list[CommitInfo]:
        """Get recent commits.

        Args:
            count: Number of commits to retrieve

        Returns:
            List of CommitInfo objects
        """
        repo = self._get_repo()
        if not repo:
            return []

        commits = []
        try:
            for commit in repo.iter_commits(max_count=count):
                commits.append(
                    CommitInfo(
                        sha=commit.hexsha[:7],
                        message=_first_line_of_message(commit.message),
                        author=commit.author.name or "Unknown",
                        date=datetime.fromtimestamp(commit.committed_date),
                    )
                )
        except (GitCommandError, ValueError) as e:
            logger.debug(f"Failed to get recent commits: {e}")

        return commits

    def get_changed_files(self, since_commit: str | None = None) -> list[str]:
        """Get files changed since a commit or recently.

        Args:
            since_commit: Optional commit SHA to compare against

        Returns:
            List of changed file paths
        """
        repo = self._get_repo()
        if not repo:
            return []

        try:
            if since_commit:
                diff = repo.commit(since_commit).diff(repo.head.commit)
            else:
                # Compare against parent of HEAD (handle initial commit with no parents)
                if not repo.head.commit.parents:
                    return []
                diff = repo.head.commit.parents[0].diff(repo.head.commit)

            # Filter out items where both a_path and b_path are None
            changed: list[str] = []
            for item in diff:
                path = item.a_path or item.b_path
                if path is not None:
                    changed.append(path)
            return changed
        except (IndexError, AttributeError, InvalidGitRepositoryError):
            return []

    def get_file_history(self, file_path: str, count: int = 5) -> list[CommitInfo]:
        """Get commit history for a specific file.

        Args:
            file_path: Path to the file relative to repo root
            count: Number of commits to retrieve

        Returns:
            List of CommitInfo objects
        """
        repo = self._get_repo()
        if not repo:
            return []

        commits = []
        try:
            for commit in repo.iter_commits(paths=file_path, max_count=count):
                commits.append(
                    CommitInfo(
                        sha=commit.hexsha[:7],
                        message=_first_line_of_message(commit.message),
                        author=commit.author.name or "Unknown",
                        date=datetime.fromtimestamp(commit.committed_date),
                    )
                )
        except (GitCommandError, ValueError) as e:
            logger.debug(f"Failed to get file history for {file_path}: {e}")

        return commits

    def get_context_summary(self) -> str:
        """Get a summary of git context for prompts.

        Returns:
            Formatted string with git context
        """
        parts = []

        status = self.get_status()
        if status:
            parts.append(f"Branch: {status.branch}")
            if status.is_dirty:
                parts.append("Status: Uncommitted changes")
                if status.modified_files:
                    parts.append(f"Modified: {', '.join(status.modified_files[:5])}")

        commits = self.get_recent_commits(3)
        if commits:
            parts.append("\nRecent commits:")
            for commit in commits:
                parts.append(f"  - [{commit.sha}] {commit.message[:50]}")

        return "\n".join(parts) if parts else "No git context available"
