"""Autorefactor command - runs Claude Code in a loop to perform refactoring."""

import asyncio
from functools import partial

import typer
from asyncer import syncify
from claude_agent_sdk import ClaudeSDKClient
from rich.console import Console
from rich.rule import Rule

from autoswe import options
from autoswe.streaming import print_message

app = typer.Typer()
console = Console()

REFACTOR_PROMPT = (
    "Analyze the project code to find a precise/targeted/elegant refactoring "
    "objective. You must analyze existing local branches and pick an objective "
    "that is not a duplicate. Perform the refactor. Use "
    "`gt create refactor/<branchname> -m ...` to create a commit. When you cannot find "
    "any refactoring objectives, output '<promise>NO REFACTORING NEEDED</promise>'"
)

NO_REFACTORING_MARKER = "<promise>NO REFACTORING NEEDED</promise>"


async def get_current_branch() -> str:
    """Get the current git branch name."""
    proc = await asyncio.create_subprocess_exec(
        "git",
        "rev-parse",
        "--abbrev-ref",
        "HEAD",
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, _ = await proc.communicate()
    return stdout.decode().strip()


async def checkout_branch(branch: str) -> None:
    """Checkout the specified git branch."""
    proc = await asyncio.create_subprocess_exec(
        "git",
        "checkout",
        branch,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    await proc.communicate()


async def run_claude_code(prompt: str) -> str:
    """Run Claude Code SDK with rich streaming output, return full text."""
    output: list[str] = []

    async with ClaudeSDKClient(options=options.claude_code_like()) as client:
        await client.query(prompt=prompt)
        async for message in client.receive_response():
            print_message(message, output=output)

    console.print()
    return "".join(output)


@app.callback(invoke_without_command=True)
@partial(syncify, raise_sync_error=False)
async def autorefactor(
    max_iterations: int = typer.Option(20, "--max", "-m", help="Maximum iterations"),
) -> None:
    """Run Claude Code to find and perform refactoring until none needed."""
    trunk_branch = await get_current_branch()
    console.print(f"[dim]Trunk branch: {trunk_branch}[/dim]")

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

        # Ensure we're back on the trunk branch for the next iteration
        current_branch = await get_current_branch()
        if current_branch != trunk_branch:
            console.print(f"[dim]Returning to trunk branch: {trunk_branch}[/dim]")
            await checkout_branch(trunk_branch)

        console.print()
        console.print("[yellow]Refactoring performed. Continuing...[/yellow]")

    console.print()
    console.print(
        f"[bold yellow]Reached max iterations ({max_iterations})[/bold yellow]"
    )
