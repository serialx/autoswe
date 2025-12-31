"""Review command for requesting codex reviews on PRs."""

import asyncio
import json
from functools import partial

import typer
from asyncer import syncify

app = typer.Typer()


async def run_gh_command(*args: str) -> str:
    """Run a gh CLI command and return stdout."""
    proc = await asyncio.create_subprocess_exec(
        "gh",
        *args,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await proc.communicate()
    if proc.returncode != 0:
        raise RuntimeError(f"gh command failed: {stderr.decode()}")
    return stdout.decode()


async def get_review_requested_prs(repo: str | None = None) -> list[dict]:
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


async def get_pr_details(pr_number: int, repo: str | None = None) -> dict:
    """Get PR details including comments and commits."""
    args = ["pr", "view", str(pr_number), "--json", "comments,commits"]
    if repo:
        args.extend(["--repo", repo])
    output = await run_gh_command(*args)
    return json.loads(output) if output.strip() else {}


async def add_pr_comment(pr_number: int, body: str, repo: str | None = None) -> None:
    """Add a comment to a PR."""
    args = ["pr", "comment", str(pr_number), "--body", body]
    if repo:
        args.extend(["--repo", repo])
    await run_gh_command(*args)


def get_last_codex_review_time(comments: list[dict]) -> str | None:
    """Get the timestamp of the last '@codex review' comment."""
    last_time = None
    for comment in comments:
        if "@codex review" in comment.get("body", ""):
            created_at = comment.get("createdAt")
            if created_at and (last_time is None or created_at > last_time):
                last_time = created_at
    return last_time


def get_latest_commit_time(commits: list[dict]) -> str | None:
    """Get the timestamp of the latest commit."""
    latest_time = None
    for commit in commits:
        committed_date = commit.get("committedDate")
        if committed_date and (latest_time is None or committed_date > latest_time):
            latest_time = committed_date
    return latest_time


def needs_review(comments: list[dict], commits: list[dict]) -> tuple[bool, str]:
    """Check if PR needs a new '@codex review' comment.

    Returns (needs_review, reason).
    """
    last_review = get_last_codex_review_time(comments)
    if last_review is None:
        return True, "No '@codex review' comment found"

    latest_commit = get_latest_commit_time(commits)
    if latest_commit and latest_commit > last_review:
        return True, "New commits after last review"

    return False, "Already reviewed, no new commits"


@app.callback(invoke_without_command=True)
@partial(syncify, raise_sync_error=False)
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
        print("No PRs requesting your review.")
        return

    print(f"Found {len(prs)} PR(s) requesting your review:\n")

    for pr in prs:
        pr_number = pr["number"]
        pr_title = pr["title"]
        pr_url = pr["url"]

        print(f"PR #{pr_number}: {pr_title}")
        print(f"  URL: {pr_url}")

        details = await get_pr_details(pr_number, repo)
        comments = details.get("comments", [])
        commits = details.get("commits", [])

        should_review, reason = needs_review(comments, commits)
        if not should_review:
            print(f"  Status: {reason}, skipping.\n")
        else:
            if dry_run:
                print(
                    f"  Status: {reason}. Would add '@codex review' comment (dry-run).\n"
                )
            elif auto or typer.confirm(
                f"  {reason}. Add '@codex review' comment?", default=True
            ):
                await add_pr_comment(pr_number, "@codex review", repo)
                print("  Status: Added '@codex review' comment.\n")
            else:
                print("  Status: Skipped.\n")
