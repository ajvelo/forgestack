# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.1.0] — 2026-04-21

### Added
- Multi-agent critique loop: Generator, Critic, Synthesizer
- Configurable consensus threshold (default 0.85)
- MCP integration for code-aware generation (dart, context7)
- SQLite persistence with session history
- Configurable design-system repo injection for UI-related tasks
- Multi-language project detection (Flutter/Dart, TypeScript, Python, Kotlin, Rust, Go, Ruby, Java, PHP)
- Typer CLI with `run`, `apply`, `repos`, `history`, `export`, `config-info` commands
- GitHub Actions CI running ruff, mypy, and pytest on Python 3.11, 3.12, 3.13

[Unreleased]: https://github.com/ajvelo/forgestack/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/ajvelo/forgestack/releases/tag/v0.1.0
