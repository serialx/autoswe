"""Shared configuration for Claude Agent SDK."""

import dataclasses
from typing import Any

from claude_agent_sdk import (
    PermissionResult,
    PermissionResultAllow,
    PermissionResultDeny,
    ToolPermissionContext,
)
from claude_agent_sdk.types import ClaudeAgentOptions


async def webfetch_wildcard(
    tool: str, input: dict[str, Any], context: ToolPermissionContext
) -> PermissionResult:
    """Custom tool permission handler that allows WebFetch wildcard."""
    print(
        f"Checking permission for tool: {tool} with input: {input} and context: {context}"
    )
    if tool == "WebFetch":
        return PermissionResultAllow()
    return PermissionResultDeny(message="Tool usage denied by can_use_tool policy.")


async def git_commands(
    tool: str, input: dict[str, Any], context: ToolPermissionContext
) -> PermissionResult:
    """Allow git read commands for reviewing branches."""
    if tool == "Bash":
        command = input.get("command", "")
        # Allow read-only git commands
        if command.startswith(("git branch", "git diff", "git log", "git show")):
            return PermissionResultAllow()
    return PermissionResultDeny(message="Tool usage denied by can_use_tool policy.")


async def refactor_commands(
    tool: str, input: dict[str, Any], context: ToolPermissionContext
) -> PermissionResult:
    """Allow commands needed for refactoring workflow."""
    if tool == "Bash":
        command = input.get("command", "")
        # Allow gt commands for creating branches/commits
        if command.startswith(
            ("gt create", "git branch", "git diff", "git log", "git show", "git add")
        ):
            return PermissionResultAllow()
    return PermissionResultDeny(message="Tool usage denied by can_use_tool policy.")


def claude_code_like() -> ClaudeAgentOptions:
    """Create ClaudeAgentOptions with claude code like configuration."""
    return ClaudeAgentOptions(
        permission_mode="acceptEdits",
        setting_sources=["user", "project", "local"],
        max_thinking_tokens=128000,
    )


def claude_code_like_webfetch_wildcard() -> ClaudeAgentOptions:
    """claude_code_like() with WebFetch wildcard permission."""
    return dataclasses.replace(claude_code_like(), can_use_tool=webfetch_wildcard)


def claude_code_like_git_review() -> ClaudeAgentOptions:
    """claude_code_like() with git read commands permission for branch review."""
    return dataclasses.replace(claude_code_like(), can_use_tool=git_commands)


def claude_code_like_refactor() -> ClaudeAgentOptions:
    """claude_code_like() with permissions for refactoring workflow (gt, git)."""
    return dataclasses.replace(claude_code_like(), can_use_tool=refactor_commands)
