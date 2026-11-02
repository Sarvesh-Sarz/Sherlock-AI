"""Investigation trace: a readable record of how Sherlock reached a conclusion.

Each event is one decision or action made during the investigation
(planning, a collection round, an assessment, research, reasoning). The
trace is observability only: it is written by the graph, copied onto the
`Investigation`, and exposed read-only through the API. Nothing reads it
to make decisions.
"""

from datetime import datetime, timezone
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class TraceStage(str, Enum):
    PLAN = "plan"
    COLLECT = "collect"
    ASSESS = "assess"
    RESEARCH = "research"
    REASON = "reason"


class TraceEvent(BaseModel):
    """One step in the investigation timeline."""

    stage: TraceStage
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    iteration: int = Field(
        0, description="Collection rounds completed when this event was recorded."
    )
    message: str = Field(..., description="Human-readable summary of what happened and why.")
    details: dict[str, Any] = Field(
        default_factory=dict,
        description="Structured specifics (tools, statuses, reasons) for the UI or tests.",
    )
