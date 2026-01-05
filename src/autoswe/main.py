"""CLI entry point for autoswe."""

import typer
from pydantic import BaseModel, Field

from autoswe import codex_review, permission, refactor, sync_command
from autoswe.structured import structured_query

app = typer.Typer()
app.add_typer(permission.app, name="permission")
app.add_typer(refactor.app, name="refactor")
app.add_typer(codex_review.app, name="codex-review")


@app.command()
@sync_command
async def main() -> None:
    """Example usage of structured_query."""

    class CompanyInfo(BaseModel):
        """Information about a company."""

        name: str = Field(description="The company name")
        founded_year: int = Field(description="Year the company was founded")
        headquarters: str = Field(description="Location of headquarters")
        key_products: list[str] = Field(description="Main products or services")

    result = await structured_query(
        prompt="Tell me about Anthropic, the AI company.",
        schema=CompanyInfo,
    )

    print(f"Company: {result.name}")
    print(f"Founded: {result.founded_year}")
    print(f"HQ: {result.headquarters}")
    print(f"Products: {', '.join(result.key_products)}")


def cli() -> None:
    """CLI entry point."""
    app()


if __name__ == "__main__":
    app()
