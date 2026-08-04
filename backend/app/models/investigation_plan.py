"""Domain model for a planner's output.

`InvestigationPlan` is what `app.planner.planner.Planner.create_plan()`
returns: the tools worth running for a given problem description, plus
enough context to explain why. A dataclass, like `Investigation` itself
— not a Pydantic model like `ToolResult` — because nothing requires it
to cross the API boundary yet. If that changes later, it gets the same
`from_domain()` schema treatment `Investigation` already has, rather
than being exposed as-is.
"""

from dataclasses import dataclass
from datetime import datetime


@dataclass
class InvestigationPlan:
    """The tools a Planner decided are worth running, and why.

    `matched_keywords` exists purely for transparency/debugging — so an
    investigation can explain *why* a given tool was planned — and isn't
    required by anything downstream today.
    """

    problem_description: str
    tools_to_execute: list[str]
    matched_keywords: list[str]
    created_at: datetime
