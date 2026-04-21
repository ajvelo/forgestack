"""Codebase reading utilities."""

from pathlib import Path
from typing import Any


class CodebaseReader:
    """Utilities for reading and analyzing codebases."""

    def __init__(self, max_file_size: int = 100_000) -> None:
        """Initialize the codebase reader.

        Args:
            max_file_size: Maximum file size in bytes to read (default 100KB)
        """
        self.max_file_size = max_file_size

    def read_file(self, path: Path, max_lines: int | None = None) -> str | None:
        """Read a file's contents.

        Args:
            path: Path to the file
            max_lines: Optional maximum number of lines to read

        Returns:
            File contents or None if file doesn't exist or is too large
        """
        if not path.exists() or not path.is_file():
            return None

        # Check file size
        if path.stat().st_size > self.max_file_size:
            return f"[File too large: {path.stat().st_size} bytes]"

        try:
            with open(path, encoding="utf-8") as f:
                if max_lines:
                    lines = []
                    for i, line in enumerate(f):
                        if i >= max_lines:
                            break
                        lines.append(line)
                    return "".join(lines)
                return f.read()
        except UnicodeDecodeError:
            return "[Binary file]"
        except Exception as e:
            return f"[Error reading file: {e}]"

    def list_directory(
        self,
        path: Path,
        pattern: str = "*",
        max_depth: int = 2,
        max_items: int = 50,
    ) -> str:
        """List directory contents in a tree format.

        Args:
            path: Directory path
            pattern: Glob pattern to match
            max_depth: Maximum depth to traverse
            max_items: Maximum items to list

        Returns:
            Tree-formatted string of directory contents
        """
        if not path.exists() or not path.is_dir():
            return ""

        lines = []
        count = 0

        def _list_recursive(current: Path, prefix: str, depth: int) -> None:
            nonlocal count
            if depth > max_depth or count >= max_items:
                return

            try:
                items = sorted(current.iterdir())
            except PermissionError:
                return

            # Separate directories and files
            dirs = [i for i in items if i.is_dir() and not i.name.startswith(".")]
            files = [i for i in items if i.is_file() and i.match(pattern)]

            for i, item in enumerate(dirs + files):
                if count >= max_items:
                    lines.append(f"{prefix}... (truncated)")
                    return

                is_last = i == len(dirs) + len(files) - 1
                connector = "└── " if is_last else "├── "
                next_prefix = prefix + ("    " if is_last else "│   ")

                if item.is_dir():
                    lines.append(f"{prefix}{connector}{item.name}/")
                    count += 1
                    _list_recursive(item, next_prefix, depth + 1)
                else:
                    lines.append(f"{prefix}{connector}{item.name}")
                    count += 1

        _list_recursive(path, "", 0)
        return "\n".join(lines)

    def get_repo_info(self, repo_path: Path) -> dict[str, Any]:
        """Get basic repository information.

        Args:
            repo_path: Path to the repository

        Returns:
            Dictionary with repository information
        """
        info: dict[str, Any] = {
            "path": str(repo_path),
            "name": repo_path.name,
            "exists": repo_path.exists(),
        }

        if not repo_path.exists():
            return info

        # Check for Flutter indicators
        pubspec = repo_path / "pubspec.yaml"
        if pubspec.exists():
            info["type"] = "flutter"
            pubspec_content = self.read_file(pubspec)
            if pubspec_content:
                info["pubspec_excerpt"] = pubspec_content[:500]

        # Get lib structure
        lib_dir = repo_path / "lib"
        if lib_dir.exists():
            info["structure"] = self.list_directory(lib_dir, "*.dart", max_depth=2)

        return info

    def find_files(
        self,
        repo_path: Path,
        pattern: str,
        max_results: int = 20,
    ) -> list[Path]:
        """Find files matching a pattern.

        Args:
            repo_path: Repository root path
            pattern: Glob pattern (e.g., "**/*.dart")
            max_results: Maximum number of results

        Returns:
            List of matching file paths
        """
        results = []
        try:
            for path in repo_path.glob(pattern):
                if path.is_file():
                    results.append(path)
                    if len(results) >= max_results:
                        break
        except Exception:
            pass

        return results

    def search_in_files(
        self,
        repo_path: Path,
        search_term: str,
        file_pattern: str = "**/*.dart",
        max_results: int = 10,
    ) -> list[dict[str, Any]]:
        """Search for a term in files.

        Args:
            repo_path: Repository root path
            search_term: Term to search for
            file_pattern: Glob pattern for files to search
            max_results: Maximum number of results

        Returns:
            List of dictionaries with file, line number, and content
        """
        results: list[dict[str, Any]] = []
        files = self.find_files(repo_path, file_pattern)

        for file_path in files:
            if len(results) >= max_results:
                break

            content = self.read_file(file_path)
            if not content or isinstance(content, str) and content.startswith("["):
                continue

            lines = content.split("\n")
            for line_num, line in enumerate(lines, 1):
                if search_term.lower() in line.lower():
                    results.append(
                        {
                            "file": str(file_path.relative_to(repo_path)),
                            "line": line_num,
                            "content": line.strip()[:100],
                        }
                    )
                    if len(results) >= max_results:
                        break

        return results
