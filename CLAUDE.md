# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

AutoSWE (Auto Software Engineer) is a CLI tool that automates developer tasks using Claude AI and the Claude Agent SDK. It runs Claude Code in automated loops to perform refactoring, documentation, and PR review workflows.

## Commands

```bash
uv sync                  # Install dependencies
uv run autoswe <command> # Run CLI
uv run pyright           # Type check
uv run ruff check .      # Lint
uv run ruff format .     # Format
uv run pytest            # Test
```

## Architecture

### Core Modules

- `main.py` - Typer CLI entry point with subcommand registration.

- `structured.py` - Pydantic wrapper for Claude Agent SDK. Converts Pydantic models to JSON schemas, returns validated instances via `structured_query()` and `structured_query_stream()`.

- `autoloop.py` - Shared workflow loop for automated branch-based tasks. Handles iteration, branch review with scoring, interactive cherry-pick, and prompt optimization analysis.

- `options.py` - ClaudeAgentOptions configuration presets with composable permission handlers for git operations.

### Workflow Commands

- `refactor.py` - Auto-refactoring workflow. Creates `refactor/*` branches with focused code improvements.

- `docs.py` - Auto-documentation workflow. Creates `docs/*` branches with documentation updates.

### Utilities

- `codex_review.py` - PR review automation. Finds PRs requesting user's review via `gh` CLI, adds `@codex review` comments.

- `permission.py` - Tool permission boundary testing.

- `streaming.py` - Rich streaming output handling for Claude Agent SDK messages.

- `git.py` - Async git command utilities.

- `cli.py` - Async subprocess execution.

All core functions are async-first. Uses `@sync_command` decorator from `__init__.py` to bridge async to sync for Typer commands.
