"""Shared configuration for Claude Agent SDK."""

from typing import Any

from claude_agent_sdk import (
    PermissionResult,
    PermissionResultAllow,
    PermissionResultDeny,
    ToolPermissionContext,
)
from claude_agent_sdk.types import ClaudeAgentOptions


async def can_use_tool(
    tool: str, input: dict[str, Any], context: ToolPermissionContext
) -> PermissionResult:
    """Custom tool permission handler that allows WebFetch wildcard."""
    print(
        f"Checking permission for tool: {tool} with input: {input} and context: {context}"
    )
    if tool == "WebFetch":
        return PermissionResultAllow()
    return PermissionResultDeny(message="Tool usage denied by can_use_tool policy.")


def create_agent_options() -> ClaudeAgentOptions:
    """Create ClaudeAgentOptions with standard configuration."""
    return ClaudeAgentOptions(
        permission_mode="acceptEdits",
        setting_sources=["user", "project", "local"],
        max_thinking_tokens=128000,
        can_use_tool=can_use_tool,
    )
