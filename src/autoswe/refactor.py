"""Autorefactor command - runs Claude Code in a loop to perform refactoring."""

import typer

from autoswe import sync_command
from autoswe.autoloop import WorkflowConfig, run_loop

app = typer.Typer()

NO_REFACTORING_MARKER = "<promise>NO REFACTORING NEEDED</promise>"

REFACTOR_PROMPT = f"""\
Analyze the project code to find a precise/targeted/elegant refactoring \
objective. You must analyze existing local branches and pick an objective \
that is not a duplicate.

PREFERRED refactoring types (prioritize these):
- Consolidate duplicate/similar functions into a single, more flexible function
- Improve type safety (e.g., replace tuple returns with NamedTuple, add \
Literals, use stricter types)
- Improve naming clarity (rename ambiguous parameters, avoid shadowing)
- Use existing constants/patterns more consistently
- Simplify complex conditionals or reduce nesting
- Remove dead code or unused imports

AVOID these refactoring types:
- Do NOT extract small utilities into separate files
- Do NOT create helpers for patterns only used in one location
- Do NOT over-modularize or split existing modules

IMPORTANT: The trunk branch is '{{trunk_branch}}'. Always create your branches from \
and compare against this trunk branch. Do NOT switch to or use 'main' or 'master' \
unless '{{trunk_branch}}' is one of those.

Perform the refactor. Create a branch called `refactor/<branchname>` with a \
commit. When you cannot find any refactoring objectives, output \
'{NO_REFACTORING_MARKER}'
"""

REVIEW_PROMPT = """\
Review all the 'refactor/*' branches in this repository. For each branch, \
analyze the changes made and evaluate:
1. Quality and elegance of the refactoring
2. Whether it duplicates another branch's work
3. Whether it introduces errors or breaks functionality
4. Overall value of the refactoring

The trunk branch is '{trunk_branch}'. Use `git branch` to list branches and \
`git diff {trunk_branch}...<branch>` to see changes. Score each branch from 1-10.
"""

PROMPT_OPTIMIZATION_PROMPT = """\
Analyze the user's feedback on refactoring branches and suggest improvements \
to the refactoring prompt.

Current refactoring prompt:
```
{current_prompt}
```

User feedback on branches:
{feedback}

Based on this feedback, identify patterns:
- What types of refactorings did the user accept (cherry-pick)?
- What types did the user reject (skip or delete)?
- Are there any clear preferences or anti-patterns?

Suggest an improved version of the refactoring prompt that:
1. Encourages the types of refactorings the user accepts
2. Discourages or excludes the types the user rejects
3. Maintains the core functionality

Output your analysis and the improved prompt clearly.
"""

REFACTOR_CONFIG = WorkflowConfig(
    branch_prefix="refactor",
    task_prompt=REFACTOR_PROMPT,
    review_prompt=REVIEW_PROMPT,
    optimization_prompt=PROMPT_OPTIMIZATION_PROMPT,
    no_more_marker=NO_REFACTORING_MARKER,
    task_noun="refactoring",
)


@app.callback(invoke_without_command=True)
@sync_command
async def autorefactor(
    max_iterations: int = typer.Option(20, "--max", "-m", help="Maximum iterations"),
    review_only: bool = typer.Option(
        False, "--review-only", "-r", help="Skip refactoring, only review branches"
    ),
) -> None:
    """Run Claude Code to find and perform refactoring until none needed."""
    await run_loop(REFACTOR_CONFIG, max_iterations, review_only)
