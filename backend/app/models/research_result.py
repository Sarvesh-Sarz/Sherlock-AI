"""Domain model for a single research result.

`ResearchResult` is what a `Researcher` (see `app.research.researcher`)
returns — one structured, citable source per result. Defined as a
Pydantic model and reused directly on the API side, the same way
`ToolResult` is (see its own docstring for the reasoning): there's one
true shape here, no internal-only fields that need hiding from the wire
format.
"""

from datetime import datetime

from pydantic import BaseModel, Field


class ResearchResult(BaseModel):
    """A single search result a Researcher returned for one query."""

    title: str
    url: str
    snippet: str
    source: str = Field(description="The result's domain, e.g. 'support.microsoft.com'.")
    retrieved_at: datetime
