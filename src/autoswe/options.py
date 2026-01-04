"""Shared configuration for Claude Agent SDK."""

import dataclasses
from collections.abc import Awaitable, Callable, Sequence
from typing import Any

from claude_agent_sdk import (
    PermissionResult,
    PermissionResultAllow,
    PermissionResultDeny,
    ToolPermissionContext,
)
from claude_agent_sdk.types import ClaudeAgentOptions

# Git command prefix constants for permission handlers
GIT_READ_COMMANDS: tuple[str, ...] = (
    "git branch",
    "git diff",
    "git log",
    "git show",
    "git checkout",
)
GIT_WRITE_COMMANDS: tuple[str, ...] = (
    "git add",
    "git commit",
    "git reset",
    "git merge",
    "git cherry-pick",
)

# Type alias for permission handler functions
PermissionHandler = Callable[
    [str, dict[str, Any], ToolPermissionContext], Awaitable[PermissionResult]
]


def create_permission_handler(
    allow_tools: Sequence[str] = (),
    allow_bash_prefixes: Sequence[str] = (),
) -> PermissionHandler:
    """Create a composable permission handler from declarative rules.

    Args:
        allow_tools: Tool names to allow unconditionally (e.g., ["WebFetch", "Read"]).
        allow_bash_prefixes: Command prefixes to allow for Bash tool
            (e.g., ["git branch", "git diff"]).

    Returns:
        An async permission handler function compatible with can_use_tool.

    Example:
        >>> handler = create_permission_handler(
        ...     allow_tools=["WebFetch"],
        ...     allow_bash_prefixes=["git log", "git diff"],
        ... )
    """

    async def handler(
        tool: str, input: dict[str, Any], context: ToolPermissionContext
    ) -> PermissionResult:
        # Check if tool is in the allow list
        if tool in allow_tools:
            return PermissionResultAllow()

        # Check Bash command prefixes
        if tool == "Bash" and allow_bash_prefixes:
            command = input.get("command", "")
            if any(command.startswith(prefix) for prefix in allow_bash_prefixes):
                return PermissionResultAllow()

        return PermissionResultDeny(message="Tool usage denied by can_use_tool policy.")

    return handler


def claude_code_like() -> ClaudeAgentOptions:
    """Create ClaudeAgentOptions with claude code like configuration."""
    return ClaudeAgentOptions(
        permission_mode="acceptEdits",
        setting_sources=["user", "project", "local"],
        max_thinking_tokens=128000,
    )


def claude_code_like_webfetch_wildcard() -> ClaudeAgentOptions:
    """claude_code_like() with WebFetch wildcard permission."""
    return dataclasses.replace(
        claude_code_like(),
        can_use_tool=create_permission_handler(allow_tools=["WebFetch"]),
    )


def claude_code_like_git_review() -> ClaudeAgentOptions:
    """claude_code_like() with git read commands permission for branch review."""
    return dataclasses.replace(
        claude_code_like(),
        can_use_tool=create_permission_handler(allow_bash_prefixes=GIT_READ_COMMANDS),
    )


def claude_code_like_refactor() -> ClaudeAgentOptions:
    """claude_code_like() with permissions for refactoring workflow (gt, git)."""
    return dataclasses.replace(
        claude_code_like(),
        can_use_tool=create_permission_handler(
            allow_bash_prefixes=[*GIT_READ_COMMANDS, *GIT_WRITE_COMMANDS],
        ),
    )


def claude_code_like_cherry_pick() -> ClaudeAgentOptions:
    """claude_code_like() with permissions for cherry-pick workflow."""
    return dataclasses.replace(
        claude_code_like(),
        can_use_tool=create_permission_handler(
            allow_bash_prefixes=[*GIT_READ_COMMANDS, *GIT_WRITE_COMMANDS],
        ),
    )
