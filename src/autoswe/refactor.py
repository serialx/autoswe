"""Autorefactor command - runs Claude Code in a loop to perform refactoring."""

import dataclasses

import typer
from claude_agent_sdk import ClaudeSDKClient
from claude_agent_sdk.types import ResultMessage
from pydantic import BaseModel, Field
from rich.console import Console
from rich.rule import Rule
from rich.table import Table

from autoswe import git, options, sync_command
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

REVIEW_PROMPT = (
    "Review all the 'refactor/*' branches in this repository. For each branch, "
    "analyze the changes made and evaluate:\n"
    "1. Quality and elegance of the refactoring\n"
    "2. Whether it duplicates another branch's work\n"
    "3. Whether it introduces errors or breaks functionality\n"
    "4. Overall value of the refactoring\n\n"
    "Use `git branch` to list branches and `git diff main...<branch>` to see "
    "changes. Score each branch from 1-10."
)


class BranchReview(BaseModel):
    """Review result for a single refactor branch."""

    branch_name: str = Field(description="Name of the branch")
    score: int = Field(description="Score from 1-10", ge=1, le=10)
    summary: str = Field(description="Brief summary of the refactoring")
    is_duplicate: bool = Field(description="Whether this duplicates another branch")
    duplicate_of: str | None = Field(
        default=None, description="Branch name this duplicates, if any"
    )
    has_errors: bool = Field(description="Whether the refactoring introduces errors")
    error_description: str | None = Field(
        default=None, description="Description of errors, if any"
    )
    recommendation: str = Field(
        description="keep, merge, or drop", pattern="^(keep|merge|drop)$"
    )


class RefactorReviewResult(BaseModel):
    """Complete review of all refactor branches."""

    branches: list[BranchReview] = Field(description="Review of each branch")
    total_branches: int = Field(description="Total number of branches reviewed")
    recommended_merges: list[str] = Field(
        description="Branch names recommended for merging"
    )
    recommended_drops: list[str] = Field(
        description="Branch names recommended for dropping"
    )


async def run_claude_code(prompt: str) -> str:
    """Run Claude Code SDK with rich streaming output, return full text."""
    output: list[str] = []

    async with ClaudeSDKClient(options=options.claude_code_like_refactor()) as client:
        await client.query(prompt=prompt)
        async for message in client.receive_response():
            print_message(message, output=output)

    console.print()
    return "".join(output)


async def review_refactor_branches() -> RefactorReviewResult | None:
    """Review all refactor branches and return structured results."""
    branches = await git.list_branches("refactor/*")
    if not branches:
        console.print("[dim]No refactor branches to review.[/dim]")
        return None

    console.print()
    console.print(Rule("[bold blue]Reviewing Refactor Branches[/bold blue]"))
    console.print(f"[dim]Found {len(branches)} refactor branches to review.[/dim]")
    console.print()

    # Configure structured output format
    agent_options = options.claude_code_like_git_review()
    agent_options = dataclasses.replace(
        agent_options,
        output_format={
            "type": "json_schema",
            "schema": RefactorReviewResult.model_json_schema(),
        },
    )

    structured_output = None
    async with ClaudeSDKClient(options=agent_options) as client:
        await client.query(prompt=REVIEW_PROMPT)
        async for message in client.receive_response():
            print_message(message)
            if isinstance(message, ResultMessage) and message.structured_output:
                structured_output = message.structured_output

    console.print()

    if structured_output is None:
        console.print("[red]No structured output received from review.[/red]")
        return None

    return RefactorReviewResult.model_validate(structured_output)


def display_review_results(result: RefactorReviewResult) -> None:
    """Display review results in a formatted table."""
    table = Table(title="Refactor Branch Review")
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


async def drop_low_scoring_branches(result: RefactorReviewResult) -> None:
    """Delete branches recommended for dropping."""
    if not result.recommended_drops:
        return

    console.print()
    console.print("[bold yellow]Dropping low-scoring branches...[/bold yellow]")
    for branch in result.recommended_drops:
        console.print(f"  Deleting {branch}...")
        await git.delete_branch(branch, force=True)
    console.print("[green]Done.[/green]")


@app.callback(invoke_without_command=True)
@sync_command
async def autorefactor(
    max_iterations: int = typer.Option(20, "--max", "-m", help="Maximum iterations"),
    review_only: bool = typer.Option(
        False, "--review-only", "-r", help="Skip refactoring, only review branches"
    ),
) -> None:
    """Run Claude Code to find and perform refactoring until none needed."""
    trunk_branch = await git.get_current_branch()
    if not review_only:
        console.print(f"[dim]Trunk branch: {trunk_branch}[/dim]")

    for i in range(max_iterations if not review_only else 0):
        console.print()
        console.print(
            Rule(f"[bold blue]Iteration {i + 1}/{max_iterations}[/bold blue]")
        )
        console.print()

        output = await run_claude_code(REFACTOR_PROMPT)

        if NO_REFACTORING_MARKER in output:
            console.print()
            console.print("[bold green]✨ No more refactoring needed.[/bold green]")
            break

        # Ensure we're back on the trunk branch for the next iteration
        current_branch = await git.get_current_branch()
        if current_branch != trunk_branch:
            console.print(f"[dim]Returning to trunk branch: {trunk_branch}[/dim]")
            await git.checkout_branch(trunk_branch)

        console.print()
        console.print("[yellow]Refactoring performed. Continuing...[/yellow]")

    else:
        if not review_only:
            console.print()
            console.print(
                f"[bold yellow]Reached max iterations ({max_iterations})[/bold yellow]"
            )

    # Review all refactor branches
    review_result = await review_refactor_branches()
    if review_result:
        display_review_results(review_result)
        await drop_low_scoring_branches(review_result)
        console.print()
        console.print("[bold green]Done![/bold green]")
