"""Shared workflow loop for automated branch-based tasks."""

from dataclasses import dataclass
from typing import Literal

import typer
from claude_agent_sdk import ClaudeSDKClient
from claude_agent_sdk.types import ClaudeAgentOptions
from pydantic import BaseModel, Field
from rich.rule import Rule
from rich.table import Table

from autoswe import git, options
from autoswe.console import console
from autoswe.streaming import print_message
from autoswe.structured import structured_query_stream

CHERRY_PICK_PROMPT = """\
Cherry-pick the changes from branch '{branch}' to current branch. \
If there are conflicts, resolve them. Output 'CHERRY_PICK_SUCCESS' when done \
or 'CHERRY_PICK_FAILED' if unable to complete.\
{feedback_section}
"""


@dataclass
class WorkflowConfig:
    """Configuration for an automated workflow."""

    branch_prefix: str  # e.g., "refactor", "docs"
    task_prompt: str  # Main prompt for finding work
    review_prompt: str  # Prompt for reviewing branches
    optimization_prompt: str  # Prompt for analyzing feedback
    no_more_marker: str  # Marker indicating no more work needed
    task_noun: str  # e.g., "refactoring", "documentation"


class BranchReview(BaseModel):
    """Review result for a single branch."""

    branch_name: str = Field(description="Name of the branch")
    score: int = Field(description="Score from 1-10", ge=1, le=10)
    summary: str = Field(description="Brief summary of the changes")
    is_duplicate: bool = Field(description="Whether this duplicates another branch")
    duplicate_of: str | None = Field(
        default=None, description="Branch name this duplicates, if any"
    )
    has_errors: bool = Field(description="Whether the changes introduce errors")
    error_description: str | None = Field(
        default=None, description="Description of errors, if any"
    )
    recommendation: Literal["keep", "merge", "drop"] = Field(
        description="keep, merge, or drop"
    )


class ReviewResult(BaseModel):
    """Complete review of all branches."""

    branches: list[BranchReview] = Field(description="Review of each branch")
    total_branches: int = Field(description="Total number of branches reviewed")
    recommended_merges: list[str] = Field(
        description="Branch names recommended for merging"
    )
    recommended_drops: list[str] = Field(
        description="Branch names recommended for dropping"
    )


async def run_streaming_query(prompt: str, agent_options: ClaudeAgentOptions) -> str:
    """Run Claude Code SDK with rich streaming output, return full text.

    Args:
        prompt: The prompt to send to Claude.
        agent_options: ClaudeAgentOptions for the query.

    Returns:
        The combined text output from the streaming response.
    """
    output: list[str] = []

    async with ClaudeSDKClient(options=agent_options) as client:
        await client.query(prompt=prompt)
        async for message in client.receive_response():
            print_message(message, output=output)

    console.print()
    return "".join(output)


async def run_task(prompt: str) -> str:
    """Run Claude Code SDK with task permissions, return full text."""
    return await run_streaming_query(prompt, options.claude_code_like_refactor())


async def run_cherry_pick_agent(
    branch: str, commit_message: str, feedback: str | None = None
) -> bool:
    """Run Claude Code to cherry-pick a branch. Returns True on success."""
    feedback_section = f"\n\nUser feedback: {feedback}" if feedback else ""
    prompt = CHERRY_PICK_PROMPT.format(branch=branch, feedback_section=feedback_section)
    output = await run_streaming_query(prompt, options.claude_code_like_cherry_pick())
    return "CHERRY_PICK_SUCCESS" in output


async def run_prompt_optimization_agent(
    config: WorkflowConfig,
    decisions: list[tuple[BranchReview, str, str | None]],
) -> None:
    """Analyze user feedback and suggest prompt improvements."""
    feedback_lines = []
    for branch, choice, user_feedback in decisions:
        action = {"y": "ACCEPTED", "d": "DELETED", "n": "SKIPPED"}.get(
            choice, "SKIPPED"
        )
        line = f"- [{action}] {branch.branch_name}: {branch.summary}"
        if user_feedback:
            line += f"\n  User feedback: {user_feedback}"
        feedback_lines.append(line)

    feedback = "\n".join(feedback_lines)
    prompt = config.optimization_prompt.format(
        current_prompt=config.task_prompt,
        feedback=feedback,
    )

    console.print()
    console.print(Rule("[bold magenta]Prompt Optimization Analysis[/bold magenta]"))
    console.print()

    async with ClaudeSDKClient(
        options=options.claude_code_like_git_review()
    ) as client:
        await client.query(prompt=prompt)
        async for message in client.receive_response():
            print_message(message)

    console.print()


async def review_branches(config: WorkflowConfig, trunk_branch: str) -> ReviewResult | None:
    """Review all branches and return structured results."""
    branch_pattern = f"{config.branch_prefix}/*"
    branches = await git.list_branches(branch_pattern)
    if not branches:
        console.print(f"[dim]No {config.branch_prefix} branches to review.[/dim]")
        return None

    console.print()
    title = config.branch_prefix.title()
    console.print(Rule(f"[bold blue]Reviewing {title} Branches[/bold blue]"))
    console.print(f"[dim]Found {len(branches)} {config.branch_prefix} branches to review.[/dim]")
    console.print()

    result: ReviewResult | None = None
    review_prompt = config.review_prompt.format(trunk_branch=trunk_branch)
    async for message, structured_result in structured_query_stream(
        prompt=review_prompt,
        schema=ReviewResult,
        agent_options=options.claude_code_like_git_review(),
    ):
        print_message(message)
        if structured_result is not None:
            result = structured_result

    console.print()

    if result is None:
        console.print("[red]No structured output received from review.[/red]")

    return result


def display_review_results(config: WorkflowConfig, result: ReviewResult) -> None:
    """Display review results in a formatted table."""
    title = config.branch_prefix.title()
    table = Table(title=f"{title} Branch Review")
    table.add_column("Branch", style="cyan")
    table.add_column("Score", justify="center")
    table.add_column("Summary")
    table.add_column("Issues", style="red")
    table.add_column("Action", style="bold")

    for branch in sorted(result.branches, key=lambda b: b.score, reverse=True):
        issues = []
        if branch.is_duplicate:
            issues.append(f"dup: {branch.duplicate_of}")
        if branch.has_errors:
            issues.append("errors")

        score_color = (
            "green" if branch.score >= 7 else "yellow" if branch.score >= 4 else "red"
        )
        action_color = (
            "green"
            if branch.recommendation == "merge"
            else "red"
            if branch.recommendation == "drop"
            else "yellow"
        )

        table.add_row(
            branch.branch_name,
            f"[{score_color}]{branch.score}[/{score_color}]",
            branch.summary[:50] + "..." if len(branch.summary) > 50 else branch.summary,
            ", ".join(issues) if issues else "-",
            f"[{action_color}]{branch.recommendation}[/{action_color}]",
        )

    console.print(table)

    if result.recommended_merges:
        console.print()
        console.print("[bold green]Recommended for merge:[/bold green]")
        for branch in result.recommended_merges:
            console.print(f"  - {branch}")

    if result.recommended_drops:
        console.print()
        console.print("[bold red]Recommended for drop:[/bold red]")
        for branch in result.recommended_drops:
            console.print(f"  - {branch}")


async def drop_low_scoring_branches(result: ReviewResult) -> None:
    """Delete branches recommended for dropping."""
    if not result.recommended_drops:
        return

    console.print()
    console.print("[bold yellow]Dropping low-scoring branches...[/bold yellow]")
    for branch in result.recommended_drops:
        console.print(f"  Deleting {branch}...")
        await git.delete_branch(branch, force=True)
    console.print("[green]Done.[/green]")


async def interactive_cherry_pick_review(
    config: WorkflowConfig,
    result: ReviewResult,
    trunk_branch: str,
) -> None:
    """Interactive review with Y/n/d prompt for each branch."""
    sorted_branches = sorted(result.branches, key=lambda b: b.score, reverse=True)

    # Phase 1: Collect all decisions
    decisions: list[tuple[BranchReview, str, str | None]] = []

    for branch in sorted_branches:
        console.print()
        console.print(Rule(f"[bold cyan]{branch.branch_name}[/bold cyan]"))
        console.print(
            f"Score: {branch.score}/10  |  Recommendation: {branch.recommendation}"
        )
        console.print(f"Summary: {branch.summary}")

        commit_msg = await git.get_branch_commits(branch.branch_name, trunk_branch)
        console.print(f"\n[dim]Commits:[/dim]\n{commit_msg}")

        diff = await git.get_branch_diff(branch.branch_name, trunk_branch)
        console.print("\n[dim]Diff:[/dim]")
        console.print(diff, markup=False)
        console.print()

        choice = typer.prompt(
            "Cherry-pick? [Y]es / [n]o / [d]elete / [yf] yes+feedback / [nf] no+feedback / [df] delete+feedback",
            default="y",
            show_default=False,
        ).lower()

        user_feedback: str | None = None
        if choice in ("yf", "nf", "df"):
            user_feedback = typer.prompt("Feedback")
            choice = choice[0]  # Normalize: 'yf' -> 'y', 'nf' -> 'n', 'df' -> 'd'

        decisions.append((branch, choice, user_feedback))

    # Phase 2: Prompt optimization analysis
    if decisions:
        await run_prompt_optimization_agent(config, decisions)

    # Phase 3: Execute all decisions
    console.print()
    console.print(Rule("[bold blue]Executing Actions[/bold blue]"))

    for branch, choice, user_feedback in decisions:
        if choice == "y":
            console.print(f"\n[cyan]Cherry-picking {branch.branch_name}...[/cyan]")
            success = await run_cherry_pick_agent(
                branch.branch_name, branch.summary, user_feedback
            )
            if success:
                await git.delete_branch(branch.branch_name, force=True)
                console.print(
                    f"[green]✓ Cherry-picked and deleted {branch.branch_name}[/green]"
                )
            else:
                console.print(
                    f"[red]✗ Cherry-pick failed for {branch.branch_name}[/red]"
                )
        elif choice == "d":
            await git.delete_branch(branch.branch_name, force=True)
            console.print(f"[yellow]Deleted {branch.branch_name}[/yellow]")
        else:
            console.print(f"[dim]Skipped {branch.branch_name}[/dim]")


async def run_loop(
    config: WorkflowConfig,
    max_iterations: int,
    review_only: bool,
) -> None:
    """Run the main workflow loop."""
    trunk_branch = await git.get_current_branch()
    if not review_only:
        console.print(f"[dim]Trunk branch: {trunk_branch}[/dim]")

    for i in range(max_iterations if not review_only else 0):
        console.print()
        console.print(
            Rule(f"[bold blue]Iteration {i + 1}/{max_iterations}[/bold blue]")
        )
        console.print()

        task_prompt = config.task_prompt.format(trunk_branch=trunk_branch)
        output = await run_task(task_prompt)

        if config.no_more_marker in output:
            console.print()
            console.print(f"[bold green]✨ No more {config.task_noun} needed.[/bold green]")
            break

        # Ensure we're back on the trunk branch for the next iteration
        current_branch = await git.get_current_branch()
        if current_branch != trunk_branch:
            console.print(f"[dim]Returning to trunk branch: {trunk_branch}[/dim]")
            await git.checkout_branch(trunk_branch)

        console.print()
        console.print(f"[yellow]{config.task_noun.title()} performed. Continuing...[/yellow]")

    else:
        if not review_only:
            console.print()
            console.print(
                f"[bold yellow]Reached max iterations ({max_iterations})[/bold yellow]"
            )

    # Review all branches
    review_result = await review_branches(config, trunk_branch)
    if review_result:
        display_review_results(config, review_result)
        await interactive_cherry_pick_review(config, review_result, trunk_branch)
        console.print()
        console.print("[bold green]Done![/bold green]")
