"""Permission checking command for autoswe."""

import json
from functools import partial

import typer
from asyncer import syncify
from claude_agent_sdk import query
from claude_agent_sdk.types import (
    AssistantMessage,
    ClaudeAgentOptions,
    ResultMessage,
    SystemMessage,
    TextBlock,
    ThinkingBlock,
    ToolResultBlock,
    ToolUseBlock,
)
from rich.console import Console

app = typer.Typer()
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


@app.command()
@partial(syncify, raise_sync_error=False)
async def check() -> None:
    """Check available tool permissions by executing a test query."""
    options = ClaudeAgentOptions(
        permission_mode="acceptEdits",
        setting_sources=["user", "project", "local"],
        max_thinking_tokens=128000,
    )

    prompt = """Your task is to test all available tools to discover permission boundaries.

For each tool you have access to, attempt to use it with a simple, safe test case.
Report whether each tool:
1. Works successfully
2. Requires permission/approval
3. Is denied or errors

Test these categories of tools if available:
- File reading (try reading a small file like README.md or pyproject.toml)
- File writing/editing (try creating a temp test file)
- Bash/shell commands (try a simple command like 'echo hello' or 'ls')
- Web/network tools (try fetching a simple URL if available)
- Any other tools you have access to

After testing each tool, provide a final summary table of:
- Tool name
- Status (allowed/denied/needs-permission)
- Any restrictions or limitations observed

Be thorough - test every tool you can find."""

    async for message in query(prompt=prompt, options=options):
        if isinstance(message, AssistantMessage):
            for block in message.content:
                if isinstance(block, TextBlock):
                    console.print(block.text)

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
            console.print(f"[yellow]⚙️ [{message.subtype}] {str(message.data)}[/yellow]")

        elif isinstance(message, ResultMessage):
            console.print(f"\n{message.result}")

    console.print()


def cli() -> None:
    """CLI entry point."""
    app()


if __name__ == "__main__":
    app()
