# AutoSWE

Auto Software Engineer - CLI tool that automates developer tasks using Claude AI and the Claude Agent SDK.

## Features

- **Auto-Refactoring**: Run Claude Code in a loop to find and perform code refactoring, with branch-based review workflow
- **Auto-Documentation**: Run Claude Code in a loop to find and improve documentation
- **Codex PR Review**: Automatically request `@codex review` on PRs assigned for your review
- **Structured Queries**: Pydantic-friendly wrapper for Claude Agent SDK's structured output
- **Permission Checker**: Test and discover tool permission boundaries

## Installation

```bash
uv sync
```

## Usage

```bash
# Auto-refactoring (creates refactor/* branches, then interactive review)
autoswe refactor
autoswe refactor --max 10           # Limit iterations
autoswe refactor --review-only      # Skip refactoring, review existing branches

# Auto-documentation (creates docs/* branches, then interactive review)
autoswe docs
autoswe docs --max 10
autoswe docs --review-only

# Codex PR review automation
autoswe codex-review --repo owner/repo --dry-run
autoswe codex-review --repo owner/repo --auto

# Check tool permissions
autoswe permission check
```

## Workflow Commands

The `refactor` and `docs` commands use a shared workflow:

1. Claude Code analyzes the codebase and creates task-specific branches
2. Each branch contains a single, focused change with a commit
3. After iterations complete, Claude reviews all branches and scores them
4. Interactive cherry-pick review: accept (y), skip (n), or delete (d) each branch
5. Prompt optimization analysis based on user decisions

## Requirements

- Python 3.13+
- [uv](https://github.com/astral-sh/uv)
- [GitHub CLI](https://cli.github.com/) (for codex-review command)
