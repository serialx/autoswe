"""Shared CLI command execution utilities for autoswe."""

import asyncio


async def run_command(command: str, *args: str) -> str:
    """Run a CLI command and return stdout.

    Args:
        command: The executable to run (e.g., "git", "gh").
        *args: Arguments to pass to the command.

    Returns:
        The command's stdout decoded as a string.

    Raises:
        RuntimeError: If the command exits with a non-zero status.
    """
    proc = await asyncio.create_subprocess_exec(
        command,
        *args,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await proc.communicate()
    if proc.returncode != 0:
        raise RuntimeError(f"{command} command failed: {stderr.decode()}")
    return stdout.decode()
