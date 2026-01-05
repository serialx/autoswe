"""Autodocs command - runs Claude Code in a loop to perform documentation."""

from typing import Literal

import typer
from claude_agent_sdk import ClaudeSDKClient
from claude_agent_sdk.types import ClaudeAgentOptions
from pydantic import BaseModel, Field
from rich.rule import Rule
from rich.table import Table

from autoswe import git, options, sync_command
from autoswe.console import console
from autoswe.streaming import print_message
from autoswe.structured import structured_query_stream

app = typer.Typer()

# Marker text that signals no more documentation is needed
NO_DOCUMENTATION_MARKER = "<promise>NO DOCUMENTATION NEEDED</promise>"

DOCS_PROMPT = f"""\
Analyze the project code to find a precise/targeted/elegant documentation \
objective. You must analyze existing local branches and pick an objective \
that is not a duplicate.

PREFERRED documentation types (prioritize these):
- Fix existing docstrings with wrong descriptions, Args, Returns, Raises
- Update existing mardown documentation that is out-of-date or incomplete
- Update existing README.md/CLAUDE.md sections that are inaccurate or out-of-date

AVOID these documentation types:
- Do NOT add docstrings to obvious/trivial functions (simple getters/setters)
- Do NOT create excessive boilerplate documentation
- Do NOT add inline comments for self-explanatory code
- Do NOT create separate documentation files beyond README.md

Perform the documentation task. Create a branch called `docs/<branchname>` with a \
commit. When you cannot find any documentation objectives, output \
'{NO_DOCUMENTATION_MARKER}'
"""

REVIEW_PROMPT = """\
Review all the 'docs/*' branches in this repository. For each branch, \
analyze the changes made and evaluate:
1. Quality and clarity of the documentation
2. Whether it duplicates another branch's work
3. Whether it introduces errors or inaccurate information
4. Overall value of the documentation

Use `git branch` to list branches and `git diff main...<branch>` to see \
changes. Score each branch from 1-10.
"""

CHERRY_PICK_PROMPT = """\
Cherry-pick the changes from branch '{branch}' to current branch. \
If there are conflicts, resolve them. Output 'CHERRY_PICK_SUCCESS' when done \
or 'CHERRY_PICK_FAILED' if unable to complete.
"""

PROMPT_OPTIMIZATION_PROMPT = """\
Analyze the user's feedback on documentation branches and suggest improvements \
to the documentation prompt.

Current documentation prompt:
```
{current_prompt}
```

User feedback on branches:
{feedback}

Based on this feedback, identify patterns:
- What types of documentation did the user accept (cherry-pick)?
- What types did the user reject (skip or delete)?
- Are there any clear preferences or anti-patterns?

Suggest an improved version of the documentation prompt that:
1. Encourages the types of documentation the user accepts
2. Discourages or excludes the types the user rejects
3. Maintains the core functionality

Output your analysis and the improved prompt clearly.
"""


class BranchReview(BaseModel):
    """Review result for a single docs branch."""

    branch_name: str = Field(description="Name of the branch")
    score: int = Field(description="Score from 1-10", ge=1, le=10)
    summary: str = Field(description="Brief summary of the documentation")
    is_duplicate: bool = Field(description="Whether this duplicates another branch")
    duplicate_of: str | None = Field(
        default=None, description="Branch name this duplicates, if any"
    )
    has_errors: bool = Field(description="Whether the documentation has errors")
    error_description: str | None = Field(
        default=None, description="Description of errors, if any"
    )
    recommendation: Literal["keep", "merge", "drop"] = Field(
        description="keep, merge, or drop"
    )


class DocsReviewResult(BaseModel):
    """Complete review of all docs branches."""

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


async def run_claude_code(prompt: str) -> str:
    """Run Claude Code SDK with docs permissions, return full text."""
    return await run_streaming_query(prompt, options.claude_code_like_refactor())


async def run_cherry_pick_agent(branch: str, commit_message: str) -> bool:
    """Run Claude Code to cherry-pick a branch. Returns True on success."""
    prompt = CHERRY_PICK_PROMPT.format(branch=branch, message=commit_message)
    output = await run_streaming_query(prompt, options.claude_code_like_cherry_pick())
    return "CHERRY_PICK_SUCCESS" in output


async def run_prompt_optimization_agent(
    decisions: list[tuple["BranchReview", str]],
) -> None:
    """Analyze user feedback and suggest prompt improvements."""
    # Build feedback summary
    feedback_lines = []
    for branch, choice in decisions:
        action = {"y": "ACCEPTED", "d": "DELETED", "n": "SKIPPED"}.get(
            choice, "SKIPPED"
        )
        feedback_lines.append(f"- [{action}] {branch.branch_name}: {branch.summary}")

    feedback = "\n".join(feedback_lines)
    prompt = PROMPT_OPTIMIZATION_PROMPT.format(
        current_prompt=DOCS_PROMPT,
        feedback=feedback,
    )

    console.print()
    console.print(Rule("[bold magenta]Prompt Optimization Analysis[/bold magenta]"))
    console.print()

    async with ClaudeSDKClient(options=options.claude_code_like_git_review()) as client:
        await client.query(prompt=prompt)
        async for message in client.receive_response():
            print_message(message)

    console.print()


async def review_docs_branches() -> DocsReviewResult | None:
    """Review all docs branches and return structured results."""
    branches = await git.list_branches("docs/*")
    if not branches:
        console.print("[dim]No docs branches to review.[/dim]")
        return None

    console.print()
    console.print(Rule("[bold blue]Reviewing Docs Branches[/bold blue]"))
    console.print(f"[dim]Found {len(branches)} docs branches to review.[/dim]")
    console.print()

    result: DocsReviewResult | None = None
    async for message, structured_result in structured_query_stream(
        prompt=REVIEW_PROMPT,
        schema=DocsReviewResult,
        agent_options=options.claude_code_like_git_review(),
    ):
        print_message(message)
        if structured_result is not None:
            result = structured_result

    console.print()

    if result is None:
        console.print("[red]No structured output received from review.[/red]")

    return result


def display_review_results(result: DocsReviewResult) -> None:
    """Display review results in a formatted table."""
    table = Table(title="Docs Branch Review")
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


async def drop_low_scoring_branches(result: DocsReviewResult) -> None:
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
    result: DocsReviewResult,
    trunk_branch: str,
) -> None:
    """Interactive review with Y/n/d prompt for each branch."""
    sorted_branches = sorted(result.branches, key=lambda b: b.score, reverse=True)

    # Phase 1: Collect all decisions
    decisions: list[tuple[BranchReview, str]] = []

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
            "Cherry-pick? [Y]es / [n]o / [d]elete",
            default="y",
            show_default=False,
        ).lower()

        decisions.append((branch, choice))

    # Phase 2: Prompt optimization analysis
    if decisions:
        await run_prompt_optimization_agent(decisions)

    # Phase 3: Execute all decisions
    console.print()
    console.print(Rule("[bold blue]Executing Actions[/bold blue]"))

    for branch, choice in decisions:
        if choice == "y":
            console.print(f"\n[cyan]Cherry-picking {branch.branch_name}...[/cyan]")
            success = await run_cherry_pick_agent(branch.branch_name, branch.summary)
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


@app.callback(invoke_without_command=True)
@sync_command
async def autodocs(
    max_iterations: int = typer.Option(20, "--max", "-m", help="Maximum iterations"),
    review_only: bool = typer.Option(
        False, "--review-only", "-r", help="Skip documentation, only review branches"
    ),
) -> None:
    """Run Claude Code to find and perform documentation until none needed."""
    trunk_branch = await git.get_current_branch()
    if not review_only:
        console.print(f"[dim]Trunk branch: {trunk_branch}[/dim]")

    for i in range(max_iterations if not review_only else 0):
        console.print()
        console.print(
            Rule(f"[bold blue]Iteration {i + 1}/{max_iterations}[/bold blue]")
        )
        console.print()

        output = await run_claude_code(DOCS_PROMPT)

        if NO_DOCUMENTATION_MARKER in output:
            console.print()
            console.print("[bold green]✨ No more documentation needed.[/bold green]")
            break

        # Ensure we're back on the trunk branch for the next iteration
        current_branch = await git.get_current_branch()
        if current_branch != trunk_branch:
            console.print(f"[dim]Returning to trunk branch: {trunk_branch}[/dim]")
            await git.checkout_branch(trunk_branch)

        console.print()
        console.print("[yellow]Documentation performed. Continuing...[/yellow]")

    else:
        if not review_only:
            console.print()
            console.print(
                f"[bold yellow]Reached max iterations ({max_iterations})[/bold yellow]"
            )

    # Review all docs branches
    review_result = await review_docs_branches()
    if review_result:
        display_review_results(review_result)
        await interactive_cherry_pick_review(review_result, trunk_branch)
        console.print()
        console.print("[bold green]Done![/bold green]")
