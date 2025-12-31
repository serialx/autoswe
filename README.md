# AutoSWE

Auto Software Engineer - CLI tool that automates developer tasks using Claude AI.

## Features

- **Structured Queries**: Pydantic-friendly wrapper for Claude Agent SDK's structured output
- **PR Review Automation**: Automatically request `@codex review` on PRs assigned for your review

## Installation

```bash
uv sync
```

## Usage

```bash
# Request codex reviews on PRs
autoswe review --repo owner/repo --dry-run

# Skip confirmation prompts
autoswe review --repo owner/repo --auto
```

## Requirements

- Python 3.13+
- [uv](https://github.com/astral-sh/uv)
- [GitHub CLI](https://cli.github.com/) (for review command)
