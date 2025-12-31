"""CLI entry point for autoswe."""

from functools import partial

import typer
from asyncer import syncify
from pydantic import BaseModel, Field

from autoswe.structured import structured_query

app = typer.Typer()


@app.command()
@partial(syncify, raise_sync_error=False)
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
