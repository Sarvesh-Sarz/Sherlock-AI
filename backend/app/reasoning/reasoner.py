"""Reasoner — the seam between evidence/research and a diagnosis.

`Reasoner` is an interface, deliberately not tied to any one model or
backend (per the project's model-strategy requirement): a future
Ollama-backed, AMD-optimized, or otherwise locally-hosted LLM reasoner
can implement this same contract and be swapped in via
`app.api.deps.get_reasoner` without `InvestigationService` — or anything
else — changing. `BaselineReasoner` (see `baseline_reasoner.py`) is the
only implementation today: deterministic and rule-based, not an LLM,
and it says so in every report it produces (see
`InvestigationReport.reasoning_method`).
"""

from abc import ABC, abstractmethod

from app.models.investigation_plan import InvestigationPlan
from app.models.investigation_report import InvestigationReport
from app.models.research_result import ResearchResult
from app.models.tool_result import ToolResult

NO_RESEARCH_NOTICE = (
    "External research was unavailable for this investigation; this report is based on locally "
    "collected evidence only."
)


class Reasoner(ABC):
    """Contract for turning a case's evidence (+ research) into a report."""

    @abstractmethod
    def investigate(
        self,
        case_id: str,
        problem_description: str,
        plan: InvestigationPlan,
        evidence: list[ToolResult],
        research: list[ResearchResult],
    ) -> InvestigationReport:
        """Produce a report for one investigation.

        `case_id` is accepted here purely as an identifier to stamp
        onto the returned report — it isn't itself something to reason
        about, unlike the other four arguments.

        Every claim in the returned report about the user's machine
        must be traceable to `evidence` (see `BaselineReasoner` for how
        that's enforced by construction, not just by convention). A
        hypothesis is never presented as a confirmed fact.

        Unlike a diagnostic tool or a Researcher, an implementation of
        this method IS allowed to raise — a future LLM-backed reasoner
        genuinely can fail (the backend is unreachable, times out, or
        returns something unusable), and that's a real, distinguishable
        failure `InvestigationService` is responsible for turning into
        a controlled `FAILED` case status rather than a fabricated
        report — not something to silently paper over here.
        """
