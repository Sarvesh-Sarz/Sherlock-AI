"""Domain model for an investigation ("case").

This is the internal representation the service and repository layer
work with. It's kept separate from the API schemas in
`app.schemas.investigation` on purpose: the wire format (what the
frontend sees) and the internal shape (what Planner/Reasoner/Memory will
eventually read and write) are allowed to evolve independently.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from uuid import uuid4


class CaseStatus(str, Enum):
    """Lifecycle states of an investigation.

    Only RECEIVED is reachable today, since nothing downstream of intake
    is implemented yet. The rest of the states describe the pipeline the
    later components (Planner, Tool Manager, Reasoner, Report Generator)
    are expected to drive the case through.
    """

    RECEIVED = "received"
    PLANNING = "planning"
    INVESTIGATING = "investigating"
    REASONING = "reasoning"
    REPORTING = "reporting"
    RESOLVED = "resolved"
    FAILED = "failed"


@dataclass
class Investigation:
    """A single investigation, from intake through to a resolved report."""

    case_id: str
    problem_description: str
    status: CaseStatus
    created_at: datetime
    updated_at: datetime
    findings: list[str] = field(default_factory=list)
    report: str | None = None

    @classmethod
    def new(cls, problem_description: str) -> "Investigation":
        """Create a freshly-received investigation with a generated case ID."""
        now = datetime.now(timezone.utc)
        return cls(
            case_id=str(uuid4()),
            problem_description=problem_description,
            status=CaseStatus.RECEIVED,
            created_at=now,
            updated_at=now,
        )
