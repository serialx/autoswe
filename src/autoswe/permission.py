"""Permission checking command for autoswe."""

from functools import partial

import typer
from asyncer import syncify
from claude_agent_sdk import ClaudeSDKClient
from rich.console import Console

from autoswe import options
from autoswe.streaming import print_message

app = typer.Typer()
console = Console()


@app.command()
@partial(syncify, raise_sync_error=False)
async def check() -> None:
    """Check available tool permissions by executing a test query."""
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
- Exact tool result if denied

Be thorough - test every tool you can find."""

    async with ClaudeSDKClient(options=options.claude_code_like()) as client:
        await client.query(prompt=prompt)
        async for message in client.receive_response():
            print_message(message, text_end="\n")

    console.print()


def cli() -> None:
    """CLI entry point."""
    app()


if __name__ == "__main__":
    app()
