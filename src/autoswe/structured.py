"""
Structured output wrapper for Claude Agent SDK's query() function.

This module provides a Pydantic-friendly wrapper that simplifies using
structured outputs with the Claude Agent SDK.
"""

import dataclasses
from typing import TypeVar, AsyncIterator, Any
from pydantic import BaseModel
from claude_agent_sdk import query
from claude_agent_sdk.types import ClaudeAgentOptions, ResultMessage, Message


T = TypeVar("T", bound=BaseModel)


def _merge_options(
    options: ClaudeAgentOptions | None,
    schema: type[BaseModel],
) -> ClaudeAgentOptions:
    """Merge user options with structured output format."""
    output_format = {
        "type": "json_schema",
        "schema": schema.model_json_schema(),
    }

    if options is None:
        return ClaudeAgentOptions(output_format=output_format)

    # Create a new options with output_format set
    return dataclasses.replace(options, output_format=output_format)


async def structured_query(
    prompt: str,
    schema: type[T],
    options: ClaudeAgentOptions | None = None,
) -> T:
    """
    Execute a query with structured output using a Pydantic schema.

    This wrapper converts a Pydantic model to a JSON schema and handles
    the response parsing automatically.

    Args:
        prompt: The prompt to send to Claude.
        schema: A Pydantic model class defining the expected output structure.
        options: Optional ClaudeAgentOptions for additional configuration.
            Note: output_format will be overwritten by the schema.

    Returns:
        An instance of the provided Pydantic model with validated data.

    Raises:
        ValueError: If no structured output is returned from the query.

    Example:
        ```python
        from pydantic import BaseModel

        class CompanyInfo(BaseModel):
            name: str
            founded_year: int
            headquarters: str

        result = await structured_query(
            prompt="Tell me about Anthropic",
            schema=CompanyInfo,
        )
        print(result.name)  # "Anthropic"
        ```
    """
    merged_options = _merge_options(options, schema)
    structured_output: dict[str, Any] | None = None

    async for message in query(prompt=prompt, options=merged_options):
        if isinstance(message, ResultMessage) and message.structured_output:
            structured_output = message.structured_output

    if structured_output is None:
        raise ValueError("No structured output received from query")

    return schema.model_validate(structured_output)


async def structured_query_stream(
    prompt: str,
    schema: type[T],
    options: ClaudeAgentOptions | None = None,
) -> AsyncIterator[tuple[Message, T | None]]:
    """
    Execute a query with structured output, yielding messages as they arrive.

    This is useful when you want to monitor progress while waiting for
    structured output.

    Args:
        prompt: The prompt to send to Claude.
        schema: A Pydantic model class defining the expected output structure.
        options: Optional ClaudeAgentOptions for additional configuration.
            Note: output_format will be overwritten by the schema.

    Yields:
        Tuples of (message, result) where result is None until the final
        message containing structured output.

    Example:
        ```python
        async for message, result in structured_query_stream(
            prompt="Analyze this code",
            schema=AnalysisResult,
        ):
            if result:
                print(f"Final result: {result}")
            else:
                print(f"Progress: {message}")
        ```
    """
    merged_options = _merge_options(options, schema)

    async for message in query(prompt=prompt, options=merged_options):
        if isinstance(message, ResultMessage) and message.structured_output:
            yield message, schema.model_validate(message.structured_output)
        else:
            yield message, None
