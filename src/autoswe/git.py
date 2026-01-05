"""Git command utilities for autoswe."""

from autoswe.cli import run_command


async def run_git_command(*args: str) -> str:
    """Run a git CLI command and return stdout."""
    return await run_command("git", *args)


async def get_current_branch() -> str:
    """Get the current git branch name."""
    output = await run_git_command("rev-parse", "--abbrev-ref", "HEAD")
    return output.strip()


async def checkout_branch(branch: str) -> None:
    """Checkout the specified git branch."""
    await run_git_command("checkout", branch)


async def list_branches(pattern: str | None = None) -> list[str]:
    """List git branches, optionally matching a pattern.

    Args:
        pattern: Optional glob pattern to filter branches (e.g., 'refactor/*').

    Returns:
        List of branch names.
    """
    args = ["branch", "--list", "--format=%(refname:short)"]
    if pattern:
        args.append(pattern)
    output = await run_git_command(*args)
    return [branch for branch in output.strip().split("\n") if branch]


async def delete_branch(branch: str, force: bool = False) -> None:
    """Delete a git branch.

    Args:
        branch: Name of the branch to delete.
        force: If True, use -D (force delete). Otherwise use -d.
    """
    flag = "-D" if force else "-d"
    await run_git_command("branch", flag, branch)


async def get_branch_commits(branch: str, base: str = "main") -> str:
    """Get formatted commit messages for a branch relative to base.

    Args:
        branch: Name of the branch to get commits from.
        base: Base branch to compare against.

    Returns:
        Formatted string of commit messages.
    """
    output = await run_git_command(
        "log", f"{base}..{branch}", "--pretty=format:%s%n%b", "--reverse"
    )
    return output.strip()


async def get_branch_diff(branch: str, base: str = "main") -> str:
    """Get unified diff for a branch relative to base.

    Args:
        branch: Name of the branch to get diff from.
        base: Base branch to compare against.

    Returns:
        Unified diff output.
    """
    output = await run_git_command("diff", f"{base}...{branch}")
    return output.strip()
