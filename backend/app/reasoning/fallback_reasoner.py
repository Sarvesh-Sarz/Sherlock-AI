"""FallbackReasoner — tries a primary `Reasoner`, falls back to a
second one if the primary fails.

This is the composition point for "use a local LLM when it's available,
but keep the deterministic baseline as a safety net": neither Reasoner
being composed needs to know the other exists, and `InvestigationService`
doesn't need to know a fallback exists at all — it receives one
`Reasoner` (see `app.api.deps.get_reasoner`) and calls `investigate()`
exactly as it always has, regardless of how many strategies are
composed behind it.
"""

import logging

from app.models.investigation_plan import InvestigationPlan
from app.models.investigation_report import InvestigationReport
from app.models.research_result import ResearchResult
from app.models.tool_result import ToolResult
from app.reasoning.reasoner import Reasoner

logger = logging.getLogger(__name__)


class FallbackReasoner(Reasoner):
    """Tries `primary`; if it raises, tries `fallback` instead.

    If `fallback` also raises, that exception propagates uncaught — a
    `FallbackReasoner` still holds to the same "may raise" contract
    every `Reasoner` does (see `Reasoner.investigate`'s docstring). Both
    configured strategies failing is a real, total reasoning failure;
    it's still `InvestigationService`'s job to turn that into a
    controlled `FAILED` case status, not this class's job to invent a
    report when it has nothing trustworthy to build one from.
    """

    def __init__(self, primary: Reasoner, fallback: Reasoner) -> None:
        self._primary = primary
        self._fallback = fallback

    def investigate(
        self,
        case_id: str,
        problem_description: str,
        plan: InvestigationPlan,
        evidence: list[ToolResult],
        research: list[ResearchResult],
    ) -> InvestigationReport:
        try:
            return self._primary.investigate(
                case_id=case_id,
                problem_description=problem_description,
                plan=plan,
                evidence=evidence,
                research=research,
            )
        except Exception as exc:  # noqa: BLE001 — deliberately broad.
            # Any primary failure — unreachable backend, timeout,
            # malformed output, anything at all — should trigger the
            # fallback, not just one specific expected exception type.
            # The fallback is the safety net; it shouldn't have gaps
            # depending on exactly how the primary happened to fail.
            logger.warning(
                "Primary reasoner (%s) failed for case %s, falling back to %s: %s",
                type(self._primary).__name__,
                case_id,
                type(self._fallback).__name__,
                exc,
                exc_info=True,
            )

        return self._fallback.investigate(
            case_id=case_id,
            problem_description=problem_description,
            plan=plan,
            evidence=evidence,
            research=research,
        )
