# ForgeStack

[![CI](https://github.com/ajvelo/forgestack/actions/workflows/ci.yml/badge.svg)](https://github.com/ajvelo/forgestack/actions/workflows/ci.yml)
![Python](https://img.shields.io/badge/python-3.11%2B-blue)
![License](https://img.shields.io/badge/license-MIT-green)
![Status](https://img.shields.io/badge/status-alpha-orange)

A CLI-only, multi-agent orchestration engine that uses Claude to analyze, critique, and improve codebases via structured multi-agent critique rounds.

![ForgeStack demo](assets/demo.gif)

## Why?

Single-shot LLM code suggestions are often plausible but subtly wrong: confidently proposing APIs that don't exist, ignoring existing patterns, or missing edge cases. ForgeStack borrows from how humans review code. One agent proposes, a second critiques with a calibrated rubric, and a third synthesises the result only once a consensus score is reached. The loop forces the model to revise rather than double down, and the final output is code-aware because agents read the target files via MCP before proposing.

## Overview

ForgeStack coordinates three specialized AI agents in a structured critique loop to produce high-quality code improvements, feature implementations, bug fixes, and architecture proposals. It is currently optimized for Flutter/Dart codebases (pubspec detection, Dart analyzer MCP integration), but the architecture is framework-agnostic: the engine auto-detects manifests for Flutter, JS/TS, Python, Rust, and Go, and the prompts are language-neutral.

### Key Features

- **Multi-Agent Critique Loop**: Generator → Critic → Synthesizer workflow with consensus-based approval
- **Consensus Threshold**: Requires ≥ 0.85 approval score (8.5/10) before accepting solutions
- **Code-Aware Generation**: Generator reads actual code files via MCP to understand existing patterns
- **Evaluation History Tracking**: Generator and Critic track score progression across rounds
- **Auto-Save & Apply**: Session output is automatically saved and can be applied to code with one command
- **Repository-Aware**: Analyzes each repo independently, respecting unique patterns and conventions
- **MCP Integration**: Uses Model Context Protocol servers configured in target repos for tooling access

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                         ForgeStack CLI                          │
├─────────────────────────────────────────────────────────────────┤
│                        Orchestrator Engine                       │
│  ┌─────────────────────────────────────────────────────────────┐│
│  │                     Critique Loop                            ││
│  │  ┌───────────┐    ┌───────────┐    ┌─────────────┐         ││
│  │  │ Generator │ -> │  Critic   │ -> │ Synthesizer │         ││
│  │  │ (Sonnet)  │    │ (Sonnet)  │    │   (Opus)    │         ││
│  │  └───────────┘    └───────────┘    └─────────────┘         ││
│  │       ↑                │                                     ││
│  │       └────────────────┘ (if score < 0.85)                  ││
│  └─────────────────────────────────────────────────────────────┘│
├─────────────────────────────────────────────────────────────────┤
│  Codebase Reader  │  MCP Client  │  Persistence  │  Git Utils  │
└─────────────────────────────────────────────────────────────────┘
```

## Agent Roles

### Generator Agent
- **Purpose**: Proposes 1-2 solution approaches for the given task
- **Capabilities**:
  - Code improvements and refactors
  - New feature implementation
  - Bug fixes
  - Architecture patterns and design proposals
  - **Reading actual code files** via MCP to understand existing patterns
- **Model**: `claude-sonnet-4-5-20250929` (temperature: 0.7)
- **Behavior**:
  - Uses MCP tools to read relevant code files before proposing
  - Receives evaluation history on revision rounds to track progress

### Critic Agent
- **Purpose**: Evaluates proposals for correctness, compatibility, and maintainability
- **Evaluation Criteria** (5 dimensions, averaged for final score):
  - Correctness and logic (0-10)
  - Architecture compatibility (0-10)
  - Code quality (0-10)
  - Completeness (0-10)
  - Risk assessment (0-10)
- **Model**: `claude-sonnet-4-5-20250929` (temperature: 0.2)
- **Output**: Dimension scores + final score (0-10) with actionable feedback
- **Behavior**:
  - Tracks previous evaluations to verify improvements
  - Calibrated scoring with explicit first-round expectations (7.0-8.5 typical)

### Synthesizer Agent
- **Purpose**: Merges final Generator output with Critic feedback into production-ready code
- **Output**:
  - Final merged proposal with complete, copy-paste ready code
  - Implementation steps with exact file paths
  - Testing recommendations
  - Risk analysis
- **Model**: `claude-opus-4-20250514` (temperature: 0.4) - Uses Opus for highest quality synthesis
- **Max Tokens**: 8192 for comprehensive output

## Installation

### Prerequisites
- **Python 3.11+** (required - the MCP SDK and type hints require Python 3.11 or higher)
- **Homebrew** (macOS) for installing Python 3.11
- **Anthropic API key** with access to Claude Sonnet and Opus models

### Setup

1. **Clone the repository:**
```bash
git clone https://github.com/ajvelo/forgestack.git
cd forgestack
```

2. **Install Python 3.11** (macOS ships with Python 3.9 which won't work):
```bash
# Install Python 3.11 via Homebrew
brew install python@3.11

# Verify installation
/opt/homebrew/bin/python3.11 --version
# Should output: Python 3.11.x
```

3. **Create virtual environment and install:**
```bash
# Create venv with Python 3.11+ (use 3.13 if available)
python3.11 -m venv .venv
# or: python3.13 -m venv .venv

# Activate venv
source .venv/bin/activate

# Install forgestack
pip install -e .
```

For development (includes pytest, mypy, ruff):
```bash
pip install -e ".[dev]"
```

4. **Configure your API key** in `~/.zshrc` (or `~/.bashrc`):
```bash
echo 'export ANTHROPIC_API_KEY="sk-ant-xxxxx"' >> ~/.zshrc
source ~/.zshrc
```

5. **Configure repository paths** in `config.yaml`:
```yaml
codebase:
  repos:
    my-app: ~/path/to/your/app
    my-library: ~/path/to/your/library
    # Add your repos here
```

### Verify Installation

```bash
# Activate venv (if not already)
source .venv/bin/activate

# Test CLI
forgestack --help

# List configured repos
forgestack repos

# Show configuration
forgestack config-info
```

## Configuration

ForgeStack uses `config.yaml` for all configuration. The API key is read from the environment variable specified in the config:

```yaml
anthropic:
  env_var: ANTHROPIC_API_KEY  # Name of env var containing the key

orchestrator:
  max_rounds: 3
  consensus_threshold: 0.85  # 8.5/10 - "Good" tier, realistic for code proposals

agents:
  generator:
    model: claude-sonnet-4-5-20250929
    temperature: 0.7
    max_tokens: 4096
  critic:
    model: claude-sonnet-4-5-20250929
    temperature: 0.2
    max_tokens: 2048
  synthesizer:
    model: claude-opus-4-20250514  # Opus for highest quality final output
    temperature: 0.4
    max_tokens: 8192

mcp:
  timeout_seconds: 600  # 10 minutes - agents take time for quality output

codebase:
  repos:
    my-app: ~/path/to/your/app
    my-library: ~/path/to/your/library
```

**Security Note**: Never store actual API keys in config files. All secrets must come from environment variables.

## CLI Usage

All commands assume you have activated the virtual environment:
```bash
source .venv/bin/activate
```

### Run a Task

You can provide the task description either as an argument or via a prompt file.

#### Using a prompt file (recommended for complex tasks)

By default, ForgeStack loads the description from `src/forgestack/prompts/.prompt.txt`:

```bash
# Edit the default prompt file
vim src/forgestack/prompts/.prompt.txt

# Run with the default prompt file
forgestack run --repo my-app --task exploration
```

You can also specify a custom prompt file:

```bash
# Use a custom prompt file from the prompts/ directory
forgestack run --repo my-app --task feature --prompt-file my_feature.txt
```

#### Using an inline description

```bash
# Code improvement
forgestack run \
  --repo my-app \
  --task code_improvement \
  "Improve error handling in the data layer"

# Feature implementation
forgestack run \
  --repo my-app \
  --task feature \
  "Implement pull-to-refresh on the items list"

# Bug fix
forgestack run \
  --repo my-app \
  --task bugfix \
  "Fix incorrect rendering of the header at small breakpoints"

# Architecture proposal
forgestack run \
  --repo my-app \
  --task architecture \
  "Design a caching layer for the API client"

# Exploration/analysis
forgestack run \
  --repo my-library \
  --task exploration \
  "Analyze the theming system and suggest improvements"
```

#### Prompt file location

Prompt files are stored in `src/forgestack/prompts/`. You can create your own prompt files there:

```
src/forgestack/prompts/
├── .prompt.txt           # Default prompt file
├── my_feature.txt        # Custom prompt file
├── generator.md          # Agent prompt (do not modify)
├── critic.md             # Agent prompt (do not modify)
└── synthesizer.md        # Agent prompt (do not modify)
```

### View History

```bash
# Show last 10 sessions
forgestack history --last 10

# Show all sessions for a repo
forgestack history --repo my-app
```

### Apply Changes

After a session completes, the output is automatically saved to `output/forgestack-{session_id}.md`. You can apply the code changes to your repository:

```bash
# Preview changes without applying (dry run)
forgestack apply output/forgestack-abc123.md --dry-run

# Apply changes (will prompt for confirmation)
forgestack apply output/forgestack-abc123.md

# Apply changes without confirmation
forgestack apply output/forgestack-abc123.md --force
```

The `apply` command:
- Parses code blocks with file paths from the synthesizer output
- Shows which files will be created or modified
- Creates parent directories if needed
- Writes the code to the target repository

**Supported code block formats** (language fence can be any supported language — `python`, `typescript`, `dart`, `go`, etc.):
```markdown
**File**: `src/app/feature.py`
**Action**: Create
\`\`\`python
# code here
\`\`\`

**File:** `src/app/feature.py`
\`\`\`python
# code here
\`\`\`

\`\`\`python:src/app/feature.py
# code here
\`\`\`

\`\`\`python
# File: src/app/feature.py
# code here
\`\`\`
```

The parser automatically detects these patterns from Claude's natural output format.

### Export Session

```bash
# Export to markdown
forgestack export --session-id abc123 --format markdown

# Export to JSON
forgestack export --session-id abc123 --format json
```

## Supported Task Types

| Task Type | Description | Use Case |
|-----------|-------------|----------|
| `code_improvement` | Refactoring and code quality | Clean up existing code, improve patterns |
| `feature` | New functionality | Implement new screens, features, integrations |
| `bugfix` | Fix defects | Resolve crashes, incorrect behavior |
| `architecture` | Design proposals | Plan system changes, design patterns |
| `exploration` | Analysis and discovery | Understand codebase, identify opportunities |

## MCP Integration

ForgeStack uses the Model Context Protocol (MCP) for tooling integration. Servers are configured in `config.yaml` and per-repo `.mcp.json` files.

### Example MCP Servers

| Server | Command | Purpose |
|--------|---------|---------|
| `dart` | `dart mcp-server` | Dart/Flutter language analysis |
| `context7` | `npx @upstash/context7-mcp` | Documentation lookup |

Any MCP server using the `stdio` transport can be configured. Add servers to `config.yaml` under `mcp.servers`.

### Per-Repository MCP Config

ForgeStack also loads MCP configuration from each target repository's `.mcp.json` file, allowing repos to define their own tooling.

**Note**: The current implementation only supports `stdio` transport. HTTP and SSE-based MCP servers are not yet supported.

## Critique Loop Behavior

### Round 1 (Initial Proposal)
1. **Generator** reads relevant code files via MCP to understand existing patterns
2. **Generator** produces 1-2 solution approaches based on task, code context, and repo structure
3. **Critic** evaluates across 5 dimensions (Correctness, Architecture, Quality, Completeness, Risk)
4. **Critic** outputs dimension scores and averaged final score
   - First-round scores typically range from 7.0-8.5

### Round 2+ (Revision)
If score < 0.85:
1. **Generator** receives:
   - Previous proposal
   - Critic feedback with specific weaknesses
   - Evaluation history showing score progression
2. **Generator** revises proposal, focusing on identified weaknesses
3. **Critic** evaluates revision:
   - References previous evaluation
   - Tracks which issues were ADDRESSED, PARTIALLY ADDRESSED, or NOT ADDRESSED
   - Adjusts score based on improvements (+0.5 to +1.5 for major fixes)

### Consensus & Synthesis
Once score ≥ 0.85 OR max rounds (3) reached:
1. **Synthesizer** (Opus) produces final output:
   - Complete, copy-paste ready code
   - Exact file paths for all changes
   - Implementation steps
   - Testing recommendations
   - Risk analysis
2. Session is persisted to database
3. **Output is auto-saved** to `output/forgestack-{session_id}.md`
4. Run `forgestack apply` to apply the code changes

### Expected Score Progression
- **Round 1**: 7.5-8.0 (with actual code context)
- **Round 2**: 8.2-8.6 (targeted fixes based on feedback)
- **Consensus**: Typically achieved by round 2 at 0.85 threshold

## Persistence

ForgeStack stores all sessions in a SQLite database for:
- Session history and replay
- Learning from past interactions
- Export and analysis

Database location: `./data/forgestack.db`

## Development

### Running Tests

```bash
pytest
```

### Type Checking

```bash
mypy src/forgestack
```

### Linting

```bash
ruff check src/forgestack
```

## Project Structure

```
forgestack/
├── pyproject.toml          # Project configuration
├── config.yaml             # Runtime configuration
├── README.md               # This file
├── data/                   # SQLite database storage
│   └── forgestack.db       # Session history database
├── output/                 # Auto-saved session outputs
│   └── forgestack-*.md     # Apply-ready output files
├── src/forgestack/
│   ├── cli/                # Typer CLI commands
│   ├── agents/             # Generator, Critic, Synthesizer
│   ├── orchestrator/       # Critique loop engine
│   ├── persistence/        # SQLite database layer
│   ├── codebase/           # Repo reading utilities
│   ├── mcp/                # MCP integration
│   ├── prompts/            # Agent prompt templates
│   │   ├── .prompt.txt     # Default task prompt file
│   │   ├── generator.md    # Generator agent prompt
│   │   ├── critic.md       # Critic agent prompt
│   │   └── synthesizer.md  # Synthesizer agent prompt
│   └── utils/              # Logging, formatting
└── tests/                  # Test suite
```

## Troubleshooting

### "No module named 'typer'" or import errors
Make sure you've activated the venv and installed the package:
```bash
source .venv/bin/activate
pip install -e .
```

### "TypeError: unsupported operand type(s) for |: 'type' and 'NoneType'"
You're using Python < 3.10. Recreate the venv with Python 3.11+:
```bash
rm -rf .venv
python3.11 -m venv .venv  # or python3.13
source .venv/bin/activate
pip install -e .
```

### "ModuleNotFoundError: No module named 'mcp'"
The MCP SDK should be installed automatically. If not:
```bash
pip install mcp
```

### API key not found
Ensure your API key is exported in your shell:
```bash
echo $ANTHROPIC_API_KEY  # Should print your key

# If empty, add to ~/.zshrc:
export ANTHROPIC_API_KEY="sk-ant-xxxxx"
source ~/.zshrc
```

### Repository not found
Check that the repo paths in `config.yaml` are correct and the directories exist:
```bash
forgestack repos  # Shows status of each configured repo
```

### Intel Mac users
If you're on an Intel Mac, the Homebrew path is different:
```bash
/usr/local/bin/python3.11  # Instead of /opt/homebrew/bin/python3.11
```

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Run tests and linting
5. Submit a pull request
