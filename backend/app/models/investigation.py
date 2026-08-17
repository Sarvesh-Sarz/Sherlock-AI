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

from app.models.investigation_plan import InvestigationPlan
from app.models.investigation_report import InvestigationReport
from app.models.tool_result import ToolResult


class CaseStatus(str, Enum):
    """Lifecycle states of an investigation.

    Only RECEIVED and INVESTIGATING are reachable today: every case is
    planned (see `app.planner.planner.Planner`) and, if the plan calls
    for it, has `cpu` run against it. The remaining states describe the
    rest of the pipeline the later components (Tool Manager, Reasoner,
    Report Generator) are expected to drive the case through.
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
    plan: InvestigationPlan | None = None
    evidence: list[ToolResult] = field(default_factory=list)
    findings: list[str] = field(default_factory=list)
    report: InvestigationReport | None = None

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

    def set_plan(self, plan: InvestigationPlan) -> None:
        """Attach the planner's output and refresh the update time."""
        self.plan = plan
        self.updated_at = datetime.now(timezone.utc)

    def add_evidence(self, result: ToolResult) -> None:
        """Attach a diagnostic tool's result and refresh the update time.

        Kept on the entity itself, rather than left to callers to mutate
        `evidence` and `updated_at` separately, so "evidence changed" and
        "the record was updated" can never drift apart.
        """
        self.evidence.append(result)
        self.updated_at = datetime.now(timezone.utc)

    def mark_status(self, status: CaseStatus) -> None:
        """Transition to a new lifecycle status and refresh the update time."""
        self.status = status
        self.updated_at = datetime.now(timezone.utc)

    def set_report(self, report: InvestigationReport) -> None:
        self.report = report
