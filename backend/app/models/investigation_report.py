"""Domain model for the output of Sherlock's reasoning stage.

`InvestigationReport` is what a `Reasoner` (see `app.reasoning.reasoner`)
produces from a case's evidence and research. Like `ToolResult` and
`ResearchResult`, it's defined as a Pydantic model and reused directly
on the API side — every field here is meant to reach the user, so there
are no internal-only fields that would call for a separate schema and
`from_domain()` translation the way `Investigation` itself needs.

The report keeps three things structurally distinct, on purpose (see
each field's docstring):

- OBSERVED FACTS — `evidence_used`, verbatim from the tools that ran.
- REASONING / HYPOTHESES — `hypotheses`, each individually confidence-
  rated and never presented as confirmed.
- RECOMMENDATIONS — `recommendations`, observational/manual guidance
  only. Sherlock never modifies the system it's investigating.
"""

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field

from app.models.research_result import ResearchResult
from app.models.tool_result import ToolResult


class Confidence(str, Enum):
    """A deliberately coarse, qualitative confidence level.

    Used for both a single hypothesis and the report as a whole. Kept
    to three plain levels rather than a numeric score: a baseline,
    rule-based reasoner (see `app.reasoning.baseline_reasoner`) can't
    honestly produce a calibrated probability, and a fake-looking
    number (e.g. "73% confidence") would overstate the precision of a
    simple threshold rule.
    """

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class Hypothesis(BaseModel):
    """One possible explanation for the reported problem.

    A hypothesis is never a confirmed fact — `confidence` exists
    specifically so it can't be mistaken for one. `supporting_evidence`
    entries must be traceable to real values in the case's evidence
    (see `app.reasoning.baseline_reasoner` for how that's enforced by
    construction, not just by convention).
    """

    title: str
    explanation: str
    supporting_evidence: list[str] = Field(default_factory=list)
    contradicting_evidence: list[str] = Field(default_factory=list)
    confidence: Confidence


class InvestigationReport(BaseModel):
    """The result of reasoning over a case's evidence (and, if
    available, external research).
    """

    case_id: str
    problem_description: str
    summary: str
    hypotheses: list[Hypothesis] = Field(default_factory=list)
    evidence_used: list[ToolResult] = Field(
        default_factory=list,
        description="The observed facts this report reasoned over — copied from the case's evidence.",
    )
    recommendations: list[str] = Field(
        default_factory=list,
        description="Observational/manual guidance only. Never an action Sherlock took or will take.",
    )
    confidence: Confidence
    research_sources: list[ResearchResult] = Field(default_factory=list)
    research_notice: str | None = Field(
        default=None,
        description="Set when external research was unavailable, so the report says so explicitly "
        "rather than silently having an empty research_sources list.",
    )
    reasoning_method: str = Field(
        description="Identifies which Reasoner implementation produced this report "
        "(e.g. 'deterministic_baseline'), so a report is never ambiguous about whether "
        "an AI model was involved."
    )
    created_at: datetime
