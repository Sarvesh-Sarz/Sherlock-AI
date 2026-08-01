"""Domain model for a diagnostic tool's result ("evidence").

`ToolResult` is the one shape every diagnostic tool returns — cpu.py
today; memory.py, disk.py, battery.py, wifi.py, startup.py later.
Callers (`InvestigationService`, the API layer, eventually the Reasoner)
can treat "a tool ran" as a single uniform event without knowing which
tool produced it or what its payload contains.

Defined here as a Pydantic model — alongside `Investigation` and
`CaseStatus` in `app.models.investigation` — rather than in
`app.schemas`, because it's reused as-is on both sides of the app: it's
what a tool returns internally *and* what the API serializes directly,
with no translation step in between. That's different from
`Investigation`, which does need one — see `app.schemas.investigation`
and its `from_domain()` mappers — because the domain entity is expected
to grow internal-only fields the API shouldn't expose. `ToolResult` has
no such concern: tool_name/status/collected_at/payload *is* the contract,
both inside the app and on the wire.
"""

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class ToolStatus(str, Enum):
    """Outcome of a single diagnostic tool run."""

    SUCCESS = "success"
    ERROR = "error"


class ToolResult(BaseModel):
    """Uniform result returned by every diagnostic tool.

    `payload` is intentionally a free-form dict rather than a per-tool
    typed model: each tool's payload shape is different (CPU frequency
    vs. disk usage vs. battery health), and typing it per tool here would
    mean this shared contract keeps changing every time a new tool is
    added — the opposite of what "reusable" is meant to buy us. Each
    tool module is responsible for documenting its own payload shape.
    """

    tool_name: str = Field(
        ..., description="Machine-readable identifier for the tool, e.g. 'cpu'."
    )
    status: ToolStatus
    collected_at: datetime
    payload: dict[str, Any] = Field(
        default_factory=dict,
        description="Tool-specific evidence on success, or error details on failure.",
    )
