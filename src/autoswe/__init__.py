"""Auto-SWE: Structured output wrapper for Claude Agent SDK."""

from functools import partial

from asyncer import syncify

from autoswe.structured import structured_query, structured_query_stream

# Decorator to convert async functions to sync for Typer commands
sync_command = partial(syncify, raise_sync_error=False)

__all__ = ["structured_query", "structured_query_stream", "sync_command"]
