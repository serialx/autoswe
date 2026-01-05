"""Codex auto-review command for requesting codex reviews on PRs."""

import json
from collections.abc import Callable, Mapping, Sequence
from typing import Any, NamedTuple, TypedDict

import typer

from autoswe import sync_command
from autoswe.cli import run_command
from autoswe.console import console

app = typer.Typer()

# The comment text used to trigger codex review
CODEX_REVIEW_COMMENT = "@codex review"


class Commit(TypedDict):
    """Commit information from GitHub API."""

    committedDate: str


class Comment(TypedDict):
    """Comment information from GitHub API."""

    body: str
    createdAt: str


class PRInfo(TypedDict):
    """PR summary from GitHub API list command."""

    number: int
    url: str
    title: str


class PRDetails(TypedDict):
    """PR details including comments and commits."""

    comments: list[Comment]
    commits: list[Commit]


class ReviewStatus(NamedTuple):
    """Result of checking whether a PR needs review."""

    should_review: bool
    reason: str


async def run_gh_command(*args: str) -> str:
    """Run a gh CLI command and return stdout."""
    return await run_command("gh", *args)


async def get_review_requested_prs(repo: str | None = None) -> list[PRInfo]:
    """Get PRs where the current user is requested as a reviewer."""
    args = [
        "pr",
        "list",
        "--json",
        "number,url,title",
        "--search",
        "review-requested:@me",
    ]
    if repo:
        args.extend(["--repo", repo])
    output = await run_gh_command(*args)
    return json.loads(output) if output.strip() else []


async def get_pr_details(pr_number: int, repo: str | None = None) -> PRDetails:
    """Get PR details including comments and commits."""
    args = ["pr", "view", str(pr_number), "--json", "comments,commits"]
    if repo:
        args.extend(["--repo", repo])
    output = await run_gh_command(*args)
    data = json.loads(output) if output.strip() else {}
    return PRDetails(comments=data.get("comments", []), commits=data.get("commits", []))


async def add_pr_comment(pr_number: int, body: str, repo: str | None = None) -> None:
    """Add a comment to a PR."""
    args = ["pr", "comment", str(pr_number), "--body", body]
    if repo:
        args.extend(["--repo", repo])
    await run_gh_command(*args)


def get_max_timestamp(
    items: Sequence[Mapping[str, Any]],
    timestamp_key: str,
    filter_fn: Callable[[Mapping[str, Any]], bool] = lambda _: True,
) -> str | None:
    """Extract the maximum timestamp from a list of dicts.

    Args:
        items: List of dicts to extract timestamps from.
        timestamp_key: Key to use for extracting the timestamp.
        filter_fn: Optional filter function to apply to items.

    Returns:
        The maximum timestamp string, or None if no timestamps found.
    """
    timestamps: list[str] = [
        ts
        for item in items
        if filter_fn(item) and (ts := item.get(timestamp_key)) is not None
    ]
    return max(timestamps, default=None)


def get_last_codex_review_time(comments: Sequence[Mapping[str, Any]]) -> str | None:
    """Get the timestamp of the last CODEX_REVIEW_COMMENT comment."""
    return get_max_timestamp(
        comments,
        "createdAt",
        filter_fn=lambda c: CODEX_REVIEW_COMMENT in c.get("body", ""),
    )


def get_latest_commit_time(commits: Sequence[Mapping[str, Any]]) -> str | None:
    """Get the timestamp of the latest commit."""
    return get_max_timestamp(commits, "committedDate")


def needs_review(comments: list[Comment], commits: list[Commit]) -> ReviewStatus:
    """Check if PR needs a new CODEX_REVIEW_COMMENT comment."""
    last_review = get_last_codex_review_time(comments)
    if last_review is None:
        return ReviewStatus(True, f"No '{CODEX_REVIEW_COMMENT}' comment found")

    latest_commit = get_latest_commit_time(commits)
    if latest_commit and latest_commit > last_review:
        return ReviewStatus(True, "New commits after last review")

    return ReviewStatus(False, "Already reviewed, no new commits")


@app.callback(invoke_without_command=True)
@sync_command
async def review(
    repo: str | None = typer.Option(
        None,
        "--repo",
        "-R",
        help="Repository in OWNER/REPO format. Uses current repo if not specified.",
    ),
    dry_run: bool = typer.Option(
        False,
        "--dry-run",
        "-n",
        help="Show what would be done without making changes.",
    ),
    auto: bool = typer.Option(
        False,
        "--auto",
        "-y",
        help="Skip confirmation prompts and add comments automatically.",
    ),
) -> None:
    """Find PRs requesting my review and add '@codex review' comment if not present."""
    prs = await get_review_requested_prs(repo)

    if not prs:
        console.print("No PRs requesting your review.")
        return

    console.print(f"Found {len(prs)} PR(s) requesting your review:\n")

    for pr in prs:
        pr_number = pr["number"]
        pr_title = pr["title"]
        pr_url = pr["url"]

        console.print(f"PR #{pr_number}: {pr_title}")
        console.print(f"  URL: {pr_url}")

        details = await get_pr_details(pr_number, repo)
        comments = details["comments"]
        commits = details["commits"]

        should_review, reason = needs_review(comments, commits)
        if not should_review:
            console.print(f"  Status: {reason}, skipping.\n")
        else:
            if dry_run:
                console.print(
                    f"  Status: {reason}. Would add '{CODEX_REVIEW_COMMENT}' comment (dry-run).\n"
                )
            elif auto or typer.confirm(
                f"  {reason}. Add '{CODEX_REVIEW_COMMENT}' comment?", default=True
            ):
                await add_pr_comment(pr_number, CODEX_REVIEW_COMMENT, repo)
                console.print(f"  Status: Added '{CODEX_REVIEW_COMMENT}' comment.\n")
            else:
                console.print("  Status: Skipped.\n")
