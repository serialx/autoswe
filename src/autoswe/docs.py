"""Autodocs command - runs Claude Code in a loop to perform documentation."""

import typer

from autoswe import sync_command
from autoswe.autoloop import WorkflowConfig, run_loop

app = typer.Typer()

NO_DOCUMENTATION_MARKER = "<promise>NO DOCUMENTATION NEEDED</promise>"

DOCS_PROMPT = f"""\
Analyze the project code to find a precise/targeted/elegant documentation \
objective. You must analyze existing local branches and pick an objective \
that is not a duplicate.

CRITICAL ACCURACY REQUIREMENT:
- ONLY document what you can VERIFY in the actual source code
- Do NOT invent examples, status strings, parameter descriptions, or values
- Before writing any documentation, READ the actual implementation to confirm details
- If you cannot verify something from the code, do NOT include it
- Quote or reference actual code when describing behavior

PREFERRED documentation types (prioritize these):
- Fix existing docstrings with wrong descriptions, Args, Returns, Raises (verify against actual function signature)
- Update existing markdown documentation that is out-of-date or incomplete
- Update existing README.md/CLAUDE.md sections that are inaccurate or out-of-date
- Remove outdated documentation that no longer matches the code

AVOID these documentation types:
- Do NOT add docstrings to obvious/trivial functions (simple getters/setters)
- Do NOT create excessive boilerplate documentation
- Do NOT add inline comments for self-explanatory code
- Do NOT create separate documentation files beyond README.md
- Do NOT fabricate examples, status messages, or parameter values
- Do NOT document assumed behavior - only verified behavior

VERIFICATION PROCESS:
1. Read the actual source code for any function/module you plan to document
2. Extract parameter names, types, and behavior directly from the implementation
3. Cross-check any examples or values against actual code usage
4. If uncertain about a detail, omit it rather than guess

IMPORTANT: The trunk branch is '{{trunk_branch}}'. Always create your branches from \
and compare against this trunk branch. Do NOT switch to or use 'main' or 'master' \
unless '{{trunk_branch}}' is one of those.

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

Use `git branch` to list branches and `git show` to see \
changes. Score each branch from 1-10.
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

DOCS_CONFIG = WorkflowConfig(
    branch_prefix="docs",
    task_prompt=DOCS_PROMPT,
    review_prompt=REVIEW_PROMPT,
    optimization_prompt=PROMPT_OPTIMIZATION_PROMPT,
    no_more_marker=NO_DOCUMENTATION_MARKER,
    task_noun="documentation",
)


@app.callback(invoke_without_command=True)
@sync_command
async def autodocs(
    max_iterations: int = typer.Option(20, "--max", "-m", help="Maximum iterations"),
    review_only: bool = typer.Option(
        False, "--review-only", "-r", help="Skip documentation, only review branches"
    ),
) -> None:
    """Run Claude Code to find and perform documentation until none needed."""
    await run_loop(DOCS_CONFIG, max_iterations, review_only)
