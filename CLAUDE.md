# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

AutoSWE (Auto Software Engineer) is a CLI tool that automates common developer tasks using Claude AI. It provides structured AI queries and automated workflows like PR review management.

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

- `structured.py` - Pydantic wrapper for Claude Agent SDK. Converts Pydantic models to JSON schemas, returns validated instances via `structured_query()` and `structured_query_stream()`.

- `main.py` - Typer CLI entry point. Uses `asyncer.syncify` to bridge async to sync.

- `review.py` - PR review automation. Finds PRs requesting user's review via `gh` CLI, adds `@codex review` comments, tracks commits to re-request after new pushes.

All core functions are async-first.
