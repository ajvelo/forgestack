# Contributing

Thanks for considering a contribution. This is a small personal project;
contributions of any size are welcome, from typo fixes to new features.

## Getting started

1. Fork the repo and clone your fork.
2. Set up a dev environment:

```bash
uv sync --extra dev
```

3. Confirm the test suite passes locally:

```bash
uv run pytest
```

## Development workflow

```bash
# format
uv run ruff format .

# lint
uv run ruff check .

# type-check
uv run mypy src/forgestack

# tests
uv run pytest
```

CI runs the same four commands on Python 3.11, 3.12, and 3.13, so run
them locally before pushing.

## Pull requests

- One logical change per PR. Keep commits clean.
- Add or update tests for any behavioural change.
- Update `CHANGELOG.md` under the `[Unreleased]` section.
- For user-visible changes, update `README.md` where applicable.
- Make sure CI is green before requesting review.

## Commit style

Conventional-commits style is encouraged but not enforced:
```
feat(cli): add --offline flag to skip Anthropic API
fix(agents): handle empty critic responses gracefully
docs: clarify config.yaml schema
```

## Reporting issues

For bugs, use the bug report template in the new-issue flow. Include
the command you ran, the full traceback, and your Python version.
