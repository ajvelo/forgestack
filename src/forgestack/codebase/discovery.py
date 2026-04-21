"""Auto-discovery of related repositories from GitHub organization."""

import asyncio
import json
import logging
import subprocess
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class RepoInfo:
    """Information about a discovered repository."""

    name: str
    description: str
    url: str
    repo_type: str  # 'frontend', 'backend', 'library', 'infra', 'unknown'
    language: str = ""
    topics: list[str] = field(default_factory=list)


@dataclass
class BackendContext:
    """Context gathered from backend repositories."""

    api_schemas: list[str] = field(default_factory=list)  # OpenAPI/GraphQL schemas
    data_models: list[str] = field(default_factory=list)  # Domain models
    service_patterns: list[str] = field(default_factory=list)  # Architecture patterns
    endpoints: list[str] = field(default_factory=list)  # API endpoints


@dataclass
class DiscoveredContext:
    """Combined context from discovered repositories."""

    repos: list[RepoInfo] = field(default_factory=list)
    backend_context: BackendContext | None = None
    design_system_context: str | None = None
    related_code_patterns: list[str] = field(default_factory=list)


class RepoDiscovery:
    """Auto-discover related repos from a GitHub org/user via the `gh` CLI.

    This class uses the GitHub CLI (gh) to discover and analyze
    repositories in the target organization, gathering context that can
    help agents understand the broader codebase ecosystem.
    """

    # Repository type detection patterns
    TYPE_PATTERNS = {
        "frontend": ["app", "web", "portal", "frontend", "ui", "flutter", "react"],
        "backend": ["api", "backend", "server", "service", "core"],
        "library": ["lib", "library", "sdk", "package", "shared", "common"],
        "infra": ["infra", "infrastructure", "deploy", "ci", "cd", "k8s", "terraform"],
    }

    def __init__(
        self,
        github_org: str = "",
        cache_ttl_minutes: int = 60,
    ) -> None:
        """Initialize the repo discovery.

        Args:
            github_org: GitHub organization to discover repos from
            cache_ttl_minutes: How long to cache discovery results
        """
        self.github_org = github_org
        self.cache_ttl = timedelta(minutes=cache_ttl_minutes)
        self._cache: dict[str, Any] = {}
        self._cache_time: datetime | None = None

    def _is_cache_valid(self) -> bool:
        """Check if the cache is still valid."""
        if self._cache_time is None:
            return False
        return datetime.now() - self._cache_time < self.cache_ttl

    async def _run_gh_command(self, args: list[str]) -> dict[str, Any] | list[Any] | None:
        """Run a gh CLI command and return parsed JSON.

        Args:
            args: Arguments to pass to gh command

        Returns:
            Parsed JSON response or None if error
        """
        try:
            cmd = ["gh"] + args
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await process.communicate()

            if process.returncode != 0:
                logger.warning(f"gh command failed: {stderr.decode()}")
                return None

            return json.loads(stdout.decode())

        except FileNotFoundError:
            logger.warning("GitHub CLI (gh) not found. Install with: brew install gh")
            return None
        except json.JSONDecodeError as e:
            logger.warning(f"Failed to parse gh output: {e}")
            return None
        except Exception as e:
            logger.warning(f"Error running gh command: {e}")
            return None

    def _classify_repo_type(self, repo: dict[str, Any]) -> str:
        """Classify a repository by type based on name and topics.

        Args:
            repo: Repository data from GitHub API

        Returns:
            Repository type classification
        """
        name = repo.get("name", "").lower()
        topics = [t.lower() for t in repo.get("repositoryTopics", {}).get("nodes", [])]
        topic_names = [t.get("topic", {}).get("name", "") for t in topics]

        # Check name patterns first
        for repo_type, patterns in self.TYPE_PATTERNS.items():
            for pattern in patterns:
                if pattern in name:
                    return repo_type

        # Check topics
        for repo_type, patterns in self.TYPE_PATTERNS.items():
            for pattern in patterns:
                if any(pattern in topic for topic in topic_names):
                    return repo_type

        # Check language for hints
        language = repo.get("primaryLanguage", {})
        if language:
            lang_name = language.get("name", "").lower()
            if lang_name in ["dart", "swift", "kotlin", "typescript"]:
                return "frontend"
            elif lang_name in ["go", "python", "java", "rust"]:
                return "backend"

        return "unknown"

    async def discover_org_repos(self, limit: int = 100) -> list[RepoInfo]:
        """List all repos in the organization using gh cli.

        Args:
            limit: Maximum number of repos to fetch

        Returns:
            List of RepoInfo objects
        """
        # Check cache first
        if self._is_cache_valid() and "repos" in self._cache:
            return self._cache["repos"]

        # Query GitHub for repos
        result = await self._run_gh_command([
            "repo", "list", self.github_org,
            "--json", "name,description,url,primaryLanguage,repositoryTopics",
            "--limit", str(limit),
        ])

        if not result or not isinstance(result, list):
            return []

        repos = []
        for repo_data in result:
            repo_type = self._classify_repo_type(repo_data)
            language = repo_data.get("primaryLanguage", {})
            topics = repo_data.get("repositoryTopics", {}).get("nodes", [])

            repos.append(RepoInfo(
                name=repo_data.get("name", ""),
                description=repo_data.get("description", "") or "",
                url=repo_data.get("url", ""),
                repo_type=repo_type,
                language=language.get("name", "") if language else "",
                topics=[t.get("topic", {}).get("name", "") for t in topics],
            ))

        # Update cache
        self._cache["repos"] = repos
        self._cache_time = datetime.now()

        logger.info(f"Discovered {len(repos)} repos in {self.github_org}")
        return repos

    async def discover_related_repos(
        self,
        task_description: str,
        task_type: str,
    ) -> list[RepoInfo]:
        """Find repos relevant to the task based on keywords/type.

        Args:
            task_description: Description of the task
            task_type: Type of task (feature, bugfix, etc.)

        Returns:
            List of relevant RepoInfo objects
        """
        all_repos = await self.discover_org_repos()

        # Keywords from task
        keywords = task_description.lower().split()

        # Filter and score repos by relevance
        scored_repos = []
        for repo in all_repos:
            score = 0

            # Score based on name matching
            for keyword in keywords:
                if keyword in repo.name.lower():
                    score += 3
                if keyword in repo.description.lower():
                    score += 1
                if any(keyword in topic for topic in repo.topics):
                    score += 2

            # Boost certain repo types based on task type
            if task_type in ["feature", "bugfix", "code_improvement"]:
                if repo.repo_type == "frontend":
                    score += 2
            if task_type == "architecture":
                if repo.repo_type in ["backend", "library"]:
                    score += 2

            if score > 0:
                scored_repos.append((repo, score))

        # Sort by score and return top results
        scored_repos.sort(key=lambda x: x[1], reverse=True)
        return [repo for repo, _ in scored_repos[:10]]

    async def gather_backend_context(
        self,
        repo_path: Path | None = None,
    ) -> BackendContext:
        """Gather API schemas and architecture patterns from backend repos.

        Args:
            repo_path: Optional specific repo path to analyze

        Returns:
            BackendContext with gathered information
        """
        context = BackendContext()

        # If we have a specific repo, analyze it
        if repo_path and repo_path.exists():
            context = await self._analyze_repo_for_backend_context(repo_path)
            return context

        # Otherwise, try to find backend repos in the org
        all_repos = await self.discover_org_repos()
        backend_repos = [r for r in all_repos if r.repo_type == "backend"]

        for repo in backend_repos[:3]:  # Limit to top 3 backend repos
            # Note: In a full implementation, we would clone/fetch these repos
            # For now, we just record their names as potential context sources
            context.service_patterns.append(
                f"Backend service: {repo.name} - {repo.description}"
            )

        return context

    async def _analyze_repo_for_backend_context(
        self,
        repo_path: Path,
    ) -> BackendContext:
        """Analyze a local repo for backend context.

        Args:
            repo_path: Path to the repository

        Returns:
            BackendContext with discovered patterns
        """
        context = BackendContext()

        # Look for OpenAPI/Swagger specs
        openapi_patterns = ["openapi.yaml", "openapi.json", "swagger.yaml", "swagger.json"]
        for pattern in openapi_patterns:
            for spec_file in repo_path.rglob(pattern):
                try:
                    content = spec_file.read_text()[:2000]  # First 2000 chars
                    context.api_schemas.append(f"OpenAPI spec ({spec_file.name}):\n{content}")
                except Exception:
                    pass

        # Look for GraphQL schemas
        for gql_file in repo_path.rglob("*.graphql"):
            try:
                content = gql_file.read_text()[:2000]
                context.api_schemas.append(f"GraphQL schema ({gql_file.name}):\n{content}")
            except Exception:
                pass

        # Look for protobuf definitions
        for proto_file in repo_path.rglob("*.proto"):
            try:
                content = proto_file.read_text()[:2000]
                context.data_models.append(f"Proto definition ({proto_file.name}):\n{content}")
            except Exception:
                pass

        # Look for common Go/Python patterns
        for pattern_file in repo_path.rglob("**/models/*.go"):
            try:
                content = pattern_file.read_text()[:1500]
                context.data_models.append(f"Go model ({pattern_file.name}):\n{content}")
            except Exception:
                pass

        return context

    async def gather_full_context(
        self,
        task_description: str,
        task_type: str,
        current_repo_path: Path,
    ) -> DiscoveredContext:
        """Gather full context for a task including related repos and patterns.

        Args:
            task_description: Description of the task
            task_type: Type of task
            current_repo_path: Path to the current working repo

        Returns:
            DiscoveredContext with all gathered information
        """
        context = DiscoveredContext()

        # Discover related repos
        context.repos = await self.discover_related_repos(task_description, task_type)

        # Gather backend context if task involves API/backend work
        backend_keywords = ["api", "endpoint", "backend", "server", "database", "model"]
        if any(kw in task_description.lower() for kw in backend_keywords):
            context.backend_context = await self.gather_backend_context()

        # Look for design system repos
        all_repos = await self.discover_org_repos()
        design_repos = [
            r for r in all_repos
            if "design" in r.name.lower() or "ui-kit" in r.name.lower()
        ]
        if design_repos:
            context.design_system_context = (
                f"Design system repos: {', '.join(r.name for r in design_repos)}"
            )

        return context

    def format_context_for_prompt(self, context: DiscoveredContext) -> str:
        """Format discovered context for inclusion in agent prompts.

        Args:
            context: Discovered context to format

        Returns:
            Formatted string for prompt inclusion
        """
        parts = []

        if context.repos:
            parts.append("## Related Repositories")
            for repo in context.repos[:5]:
                parts.append(f"- **{repo.name}** ({repo.repo_type}): {repo.description}")

        if context.backend_context:
            bc = context.backend_context
            if bc.api_schemas:
                parts.append("\n## API Context")
                for schema in bc.api_schemas[:2]:
                    parts.append(f"```\n{schema[:500]}...\n```")
            if bc.service_patterns:
                parts.append("\n## Service Patterns")
                for pattern in bc.service_patterns[:3]:
                    parts.append(f"- {pattern}")

        if context.design_system_context:
            parts.append(f"\n## Design System\n{context.design_system_context}")

        return "\n".join(parts) if parts else ""
