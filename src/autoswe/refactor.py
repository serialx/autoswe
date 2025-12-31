"""Autorefactor command - runs Claude Code in a loop to perform refactoring."""

import json
from functools import partial

import typer
from asyncer import syncify
from claude_agent_sdk import query
from claude_agent_sdk.types import (
    AssistantMessage,
    ResultMessage,
    SystemMessage,
    TextBlock,
    ThinkingBlock,
    ToolResultBlock,
    ToolUseBlock,
)
from rich.console import Console
from rich.rule import Rule

app = typer.Typer()
console = Console()

REFACTOR_PROMPT = """Analyze the project code to find a precise/targeted/elegant refactoring objective. You must analyze existing local branches and pick an objective that is not a duplicate. Perform the refactor. Use `gt create <branchname> -m ...` to create a commit. When you cannot find any refactoring objectives, output '<promise>NO REFACTORING NEEDED</promise>'"""

NO_REFACTORING_MARKER = "<promise>NO REFACTORING NEEDED</promise>"


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


async def run_claude_code(prompt: str) -> str:
    """Run Claude Code SDK with rich streaming output, return full text."""
    full_output: list[str] = []

    async for message in query(prompt=prompt):
        if isinstance(message, AssistantMessage):
            for block in message.content:
                if isinstance(block, TextBlock):
                    console.print(block.text, end="")
                    full_output.append(block.text)

                elif isinstance(block, ThinkingBlock):
                    console.print(f"[dim italic]💭 {truncate(block.thinking, 300)}[/dim italic]")

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
            console.print(f"[yellow]⚙️ [{message.subtype}] {truncate(str(message.data), 200)}[/yellow]")

        elif isinstance(message, ResultMessage):
            if message.result:
                console.print(f"\n{message.result}")
                full_output.append(message.result)

    console.print()
    return "".join(full_output)


@app.callback(invoke_without_command=True)
@partial(syncify, raise_sync_error=False)
async def autorefactor(
    max_iterations: int = typer.Option(20, "--max", "-m", help="Maximum iterations"),
) -> None:
    """Run Claude Code to find and perform refactoring until none needed."""
    for i in range(max_iterations):
        console.print()
        console.print(Rule(f"[bold blue]Iteration {i + 1}/{max_iterations}[/bold blue]"))
        console.print()

        output = await run_claude_code(REFACTOR_PROMPT)

        if NO_REFACTORING_MARKER in output:
            console.print()
            console.print("[bold green]✨ No more refactoring needed. Done![/bold green]")
            return

        console.print()
        console.print("[yellow]Refactoring performed. Continuing...[/yellow]")

    console.print()
    console.print(f"[bold yellow]Reached max iterations ({max_iterations})[/bold yellow]")
