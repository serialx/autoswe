"""Autorefactor command - runs Claude Code in a loop to perform refactoring."""

from functools import partial

import typer
from asyncer import syncify
from claude_agent_sdk import query
from rich.console import Console
from rich.rule import Rule

from autoswe.streaming import print_message

app = typer.Typer()
console = Console()

REFACTOR_PROMPT = """Analyze the project code to find a precise/targeted/elegant refactoring objective. You must analyze existing local branches and pick an objective that is not a duplicate. Perform the refactor. Use `gt create <branchname> -m ...` to create a commit. When you cannot find any refactoring objectives, output '<promise>NO REFACTORING NEEDED</promise>'"""

NO_REFACTORING_MARKER = "<promise>NO REFACTORING NEEDED</promise>"


async def run_claude_code(prompt: str) -> str:
    """Run Claude Code SDK with rich streaming output, return full text."""
    output: list[str] = []

    async for message in query(prompt=prompt):
        print_message(message, output=output)

    console.print()
    return "".join(output)


@app.callback(invoke_without_command=True)
@partial(syncify, raise_sync_error=False)
async def autorefactor(
    max_iterations: int = typer.Option(20, "--max", "-m", help="Maximum iterations"),
) -> None:
    """Run Claude Code to find and perform refactoring until none needed."""
    for i in range(max_iterations):
        console.print()
        console.print(
            Rule(f"[bold blue]Iteration {i + 1}/{max_iterations}[/bold blue]")
        )
        console.print()

        output = await run_claude_code(REFACTOR_PROMPT)

        if NO_REFACTORING_MARKER in output:
            console.print()
            console.print(
                "[bold green]✨ No more refactoring needed. Done![/bold green]"
            )
            return

        console.print()
        console.print("[yellow]Refactoring performed. Continuing...[/yellow]")

    console.print()
    console.print(
        f"[bold yellow]Reached max iterations ({max_iterations})[/bold yellow]"
    )
