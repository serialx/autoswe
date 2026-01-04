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
