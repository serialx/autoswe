"""Streaming message handling for Claude Agent SDK output."""

import json
from dataclasses import dataclass
from typing import Any

from rich.markup import escape

from claude_agent_sdk.types import (
    AssistantMessage,
    Message,
    ResultMessage,
    SystemMessage,
    TextBlock,
    ThinkingBlock,
    ToolResultBlock,
    ToolUseBlock,
)

from autoswe.console import console

# Truncation length constants for preview displays
DEFAULT_TRUNCATE_LENGTH = 200
THINKING_PREVIEW_LENGTH = 300
TOOL_RESULT_PREVIEW_LENGTH = 300
TOOL_INPUT_PREVIEW_LENGTH = 500


def truncate(text: str, max_length: int = DEFAULT_TRUNCATE_LENGTH) -> str:
    """Truncate text to max_length, adding ellipsis if needed."""
    if len(text) <= max_length:
        return text
    return text[:max_length] + "..."


def format_tool_input(tool_input: dict) -> str:
    """Format tool input for display."""
    try:
        formatted = json.dumps(tool_input, indent=2, ensure_ascii=False)
        return truncate(formatted, TOOL_INPUT_PREVIEW_LENGTH)
    except Exception:
        return truncate(str(tool_input), TOOL_INPUT_PREVIEW_LENGTH)


@dataclass
class PrintContext:
    """Context passed to block handlers for printing."""

    output: list[str] | None = None
    text_end: str = ""


def _handle_text_block(block: TextBlock, ctx: PrintContext) -> None:
    """Handle TextBlock printing."""
    console.print(block.text, end=ctx.text_end)
    if ctx.output is not None:
        ctx.output.append(block.text)


def _handle_thinking_block(block: ThinkingBlock, ctx: PrintContext) -> None:
    """Handle ThinkingBlock printing."""
    thinking_preview = truncate(block.thinking, THINKING_PREVIEW_LENGTH)
    console.print(f"[dim italic]💭 {escape(thinking_preview)}[/dim italic]")


def _handle_tool_use_block(block: ToolUseBlock, ctx: PrintContext) -> None:
    """Handle ToolUseBlock printing."""
    console.print(f"[bold cyan]🔧 {block.name}[/bold cyan]", end="")
    if block.input:
        input_preview = format_tool_input(block.input)
        console.print(f" [dim]{escape(input_preview)}[/dim]")
    else:
        console.print()


def _handle_tool_result_block(block: ToolResultBlock, ctx: PrintContext) -> None:
    """Handle ToolResultBlock printing."""
    if not block.content:
        return
    content_str = (
        block.content
        if isinstance(block.content, str)
        else json.dumps(block.content, ensure_ascii=False)
    )
    result_text = escape(truncate(content_str, TOOL_RESULT_PREVIEW_LENGTH))
    if block.is_error:
        console.print(f"[red]❌ {result_text}[/red]")
    else:
        console.print(f"[green]✅ {result_text}[/green]")


# Block type to handler dispatch table
_BLOCK_HANDLERS: dict[type, Any] = {
    TextBlock: _handle_text_block,
    ThinkingBlock: _handle_thinking_block,
    ToolUseBlock: _handle_tool_use_block,
    ToolResultBlock: _handle_tool_result_block,
}


def _handle_assistant_message(message: AssistantMessage, ctx: PrintContext) -> None:
    """Handle AssistantMessage by dispatching to block handlers."""
    needs_newline = False

    for block in message.content:
        # Add newline before non-text block if previous text didn't end with one
        if needs_newline and not isinstance(block, TextBlock):
            console.print()
            needs_newline = False

        handler = _BLOCK_HANDLERS.get(type(block))
        if handler:
            handler(block, ctx)

        # Track if we need a newline (text block printed without trailing newline)
        if isinstance(block, TextBlock):
            needs_newline = ctx.text_end == "" and not block.text.endswith("\n")
        else:
            needs_newline = False

    # Add trailing newline if message ends with text that has no newline
    if needs_newline:
        console.print()


def _handle_system_message(message: SystemMessage, ctx: PrintContext) -> None:
    """Handle SystemMessage printing."""
    console.print(f"[yellow]⚙️ [{message.subtype}] {escape(str(message.data))}[/yellow]")


def _handle_result_message(message: ResultMessage, ctx: PrintContext) -> None:
    """Handle ResultMessage printing."""
    if message.result:
        console.print(f"\n{message.result}")
        if ctx.output is not None:
            ctx.output.append(message.result)


# Message type to handler dispatch table
_MESSAGE_HANDLERS: dict[type, Any] = {
    AssistantMessage: _handle_assistant_message,
    SystemMessage: _handle_system_message,
    ResultMessage: _handle_result_message,
}


def print_message(
    message: Message,
    output: list[str] | None = None,
    text_end: str = "",
) -> None:
    """Print a streaming message with rich formatting.

    Args:
        message: The message from Claude Agent SDK query stream.
        output: Optional list to collect text output (TextBlock and ResultMessage).
        text_end: End string for TextBlock printing (default: "" for streaming).
    """
    ctx = PrintContext(output=output, text_end=text_end)
    handler = _MESSAGE_HANDLERS.get(type(message))
    if handler:
        handler(message, ctx)
