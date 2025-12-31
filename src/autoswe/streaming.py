"""Streaming message handling for Claude Agent SDK output."""

import json

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
from rich.console import Console

console = Console()


def truncate(text: str, max_length: int = 200) -> str:
    """Truncate text to max_length, adding ellipsis if needed."""
    if len(text) <= max_length:
        return text
    return text[:max_length] + "..."


def format_tool_input(tool_input: dict) -> str:
    """Format tool input for display."""
    try:
        formatted = json.dumps(tool_input, indent=2, ensure_ascii=False)
        return truncate(formatted, 500)
    except Exception:
        return truncate(str(tool_input), 500)


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
    if isinstance(message, AssistantMessage):
        for block in message.content:
            if isinstance(block, TextBlock):
                console.print(block.text, end=text_end)
                if output is not None:
                    output.append(block.text)

            elif isinstance(block, ThinkingBlock):
                console.print(
                    f"[dim italic]💭 {truncate(block.thinking, 300)}[/dim italic]"
                )

            elif isinstance(block, ToolUseBlock):
                console.print(f"[bold cyan]🔧 {block.name}[/bold cyan]", end="")
                if block.input:
                    input_preview = format_tool_input(block.input)
                    console.print(f" [dim]{input_preview}[/dim]")
                else:
                    console.print()

            elif isinstance(block, ToolResultBlock):
                if block.content:
                    content_str = (
                        block.content
                        if isinstance(block.content, str)
                        else json.dumps(block.content, ensure_ascii=False)
                    )
                    result_text = truncate(content_str, 300)
                    if block.is_error:
                        console.print(f"[red]❌ {result_text}[/red]")
                    else:
                        console.print(f"[green]✅ {result_text}[/green]")

    elif isinstance(message, SystemMessage):
        console.print(
            f"[yellow]⚙️ [{message.subtype}] {truncate(str(message.data), 200)}[/yellow]"
        )

    elif isinstance(message, ResultMessage):
        if message.result:
            console.print(f"\n{message.result}")
            if output is not None:
                output.append(message.result)
