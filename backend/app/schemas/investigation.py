"""API schemas for the investigation endpoints.

These define the wire format only. Mapping to/from the internal
`Investigation` domain model happens explicitly via the `from_domain`
classmethods below, rather than by returning domain objects directly
from the API layer — so the two are free to diverge as the domain model
grows fields the API shouldn't expose (or vice versa).
"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.investigation import CaseStatus, Investigation
from app.models.tool_result import ToolResult


class InvestigationRequest(BaseModel):
    """Body of a request to open a new investigation."""

    problem_description: str = Field(
        ...,
        min_length=1,
        max_length=2000,
        description="Plain-language description of the problem, as typed by the user.",
        examples=["My laptop becomes slow after startup."],
    )

    model_config = ConfigDict(str_strip_whitespace=True)


class InvestigationResponse(BaseModel):
    """Returned immediately after an investigation is opened."""

    case_id: str
    status: CaseStatus
    problem_description: str
    created_at: datetime
    evidence: list[ToolResult] = Field(default_factory=list)
    message: str = "Investigation started. Reasoning and reporting are not implemented yet."

    @classmethod
    def from_domain(cls, investigation: Investigation) -> "InvestigationResponse":
        return cls(
            case_id=investigation.case_id,
            status=investigation.status,
            problem_description=investigation.problem_description,
            created_at=investigation.created_at,
            evidence=investigation.evidence,
        )


class InvestigationStatus(BaseModel):
    """Current state of an investigation, returned by the status endpoint."""

    case_id: str
    status: CaseStatus
    problem_description: str
    created_at: datetime
    updated_at: datetime
    evidence: list[ToolResult] = Field(default_factory=list)
    findings: list[str] = Field(default_factory=list)
    report: str | None = None

    @classmethod
    def from_domain(cls, investigation: Investigation) -> "InvestigationStatus":
        return cls(
            case_id=investigation.case_id,
            status=investigation.status,
            problem_description=investigation.problem_description,
            created_at=investigation.created_at,
            updated_at=investigation.updated_at,
            evidence=investigation.evidence,
            findings=investigation.findings,
            report=investigation.report,
        )
