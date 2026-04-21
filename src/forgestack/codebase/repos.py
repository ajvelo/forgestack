"""Repository resolution utilities."""

from pathlib import Path

from forgestack.config import ForgeStackConfig

# Known dependency manifests, in detection order. The first match wins.
PROJECT_MANIFESTS: tuple[tuple[str, str], ...] = (
    ("pubspec.yaml", "flutter"),
    ("package.json", "javascript"),
    ("pyproject.toml", "python"),
    ("requirements.txt", "python"),
    ("Cargo.toml", "rust"),
    ("go.mod", "go"),
    ("Gemfile", "ruby"),
    ("pom.xml", "java"),
    ("build.gradle", "java"),
    ("build.gradle.kts", "kotlin"),
    ("composer.json", "php"),
)


class RepoResolver:
    """Resolves repository keys to filesystem paths."""

    def __init__(self, config: ForgeStackConfig) -> None:
        """Initialize the repository resolver.

        Args:
            config: ForgeStack configuration containing repo mappings
        """
        self.config = config

    def resolve(self, repo_key: str) -> Path:
        """Resolve a repository key to its filesystem path.

        Args:
            repo_key: The repository key (e.g., "my-app", "my-library")

        Returns:
            Absolute Path to the repository

        Raises:
            ValueError: If the repository key is not configured
        """
        return self.config.codebase.get_repo_path(repo_key)

    def list_repos(self) -> list[str]:
        """List all configured repository keys.

        Returns:
            List of repository keys
        """
        return self.config.codebase.list_repos()

    def validate_repo(self, repo_key: str) -> tuple[bool, str]:
        """Validate that a repository exists and is accessible.

        A repository is considered valid if the path exists, is a directory,
        and contains a recognised project manifest (e.g. pubspec.yaml,
        package.json, pyproject.toml, Cargo.toml, go.mod, ...).

        Args:
            repo_key: The repository key to validate

        Returns:
            Tuple of (is_valid, message)
        """
        try:
            path = self.resolve(repo_key)
        except ValueError as e:
            return False, str(e)

        if not path.exists():
            return False, f"Repository path does not exist: {path}"

        if not path.is_dir():
            return False, f"Repository path is not a directory: {path}"

        project_type = detect_project_type(path)
        if project_type is None:
            manifest_list = ", ".join(m for m, _ in PROJECT_MANIFESTS)
            return (
                False,
                f"No recognised project manifest at {path} (looked for: {manifest_list})",
            )

        return True, f"Repository valid ({project_type}): {path}"

    def get_repo_info(self, repo_key: str) -> dict:
        """Get basic information about a repository.

        Args:
            repo_key: The repository key

        Returns:
            Dictionary with repository information
        """
        path = self.resolve(repo_key)

        info: dict = {
            "key": repo_key,
            "path": str(path),
            "exists": path.exists(),
        }

        if path.exists():
            info["project_type"] = detect_project_type(path)
            info["has_lib"] = (path / "lib").exists() or (path / "src").exists()
            info["has_tests"] = any(
                (path / d).exists() for d in ("test", "tests", "__tests__", "spec")
            )

        return info


def detect_project_type(path: Path) -> str | None:
    """Return the project type for `path`, or None if no manifest is found."""
    for manifest, project_type in PROJECT_MANIFESTS:
        if (path / manifest).exists():
            return project_type
    return None
