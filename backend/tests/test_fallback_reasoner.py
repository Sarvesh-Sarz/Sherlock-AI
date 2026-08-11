"""Tests for FallbackReasoner — the primary/fallback composition, tested
against fakes so it doesn't matter which real Reasoner implementations
end up composed via app.api.deps.get_reasoner.
"""

from datetime import datetime, timezone

import pytest

from app.models.investigation_plan import InvestigationPlan
from app.models.investigation_report import Confidence, InvestigationReport
from app.models.research_result import ResearchResult
from app.models.tool_result import ToolResult
from app.reasoning.fallback_reasoner import FallbackReasoner


def _report(reasoning_method: str) -> InvestigationReport:
    return InvestigationReport(
        case_id="case-1",
        problem_description="Anything.",
        summary="summary",
        hypotheses=[],
        evidence_used=[],
        recommendations=[],
        confidence=Confidence.LOW,
        research_sources=[],
        research_notice=None,
        reasoning_method=reasoning_method,
        created_at=datetime.now(timezone.utc),
    )


def _plan() -> InvestigationPlan:
    return InvestigationPlan(
        problem_description="Anything.",
        tools_to_execute=[],
        matched_keywords=[],
        created_at=datetime.now(timezone.utc),
    )


class _StubReasoner:
    def __init__(self, report: InvestigationReport | None = None, raises: Exception | None = None) -> None:
        self._report = report
        self._raises = raises
        self.was_called = False

    def investigate(
        self,
        case_id: str,
        problem_description: str,
        plan: InvestigationPlan,
        evidence: list[ToolResult],
        research: list[ResearchResult],
    ) -> InvestigationReport:
        self.was_called = True
        if self._raises is not None:
            raise self._raises
        assert self._report is not None
        return self._report


def _investigate(reasoner: FallbackReasoner) -> InvestigationReport:
    return reasoner.investigate(
        case_id="case-1", problem_description="Anything.", plan=_plan(), evidence=[], research=[]
    )


def test_returns_the_primarys_report_when_it_succeeds() -> None:
    primary = _StubReasoner(report=_report("primary"))
    fallback = _StubReasoner(report=_report("fallback"))

    result = _investigate(FallbackReasoner(primary=primary, fallback=fallback))

    assert result.reasoning_method == "primary"
    assert fallback.was_called is False


def test_falls_back_when_the_primary_raises() -> None:
    primary = _StubReasoner(raises=RuntimeError("Ollama unreachable"))
    fallback = _StubReasoner(report=_report("fallback"))

    result = _investigate(FallbackReasoner(primary=primary, fallback=fallback))

    assert result.reasoning_method == "fallback"
    assert fallback.was_called is True


def test_falls_back_regardless_of_the_primarys_exception_type() -> None:
    """The primary can fail in ways that don't share a common exception
    type (network error, JSON error, validation error) — the fallback
    must trigger for all of them, not just one expected type.
    """
    for exc in (ConnectionError("network"), ValueError("bad json"), KeyError("missing field")):
        primary = _StubReasoner(raises=exc)
        fallback = _StubReasoner(report=_report("fallback"))

        result = _investigate(FallbackReasoner(primary=primary, fallback=fallback))

        assert result.reasoning_method == "fallback"


def test_propagates_if_both_primary_and_fallback_fail() -> None:
    primary = _StubReasoner(raises=RuntimeError("primary down"))
    fallback = _StubReasoner(raises=RuntimeError("fallback also down"))

    with pytest.raises(RuntimeError, match="fallback also down"):
        _investigate(FallbackReasoner(primary=primary, fallback=fallback))


def test_both_reasoners_are_invoked_when_the_primary_fails() -> None:
    """The fallback isn't given a degraded or different view of the
    case just because the primary failed first.
    """
    primary = _StubReasoner(raises=RuntimeError("boom"))
    fallback = _StubReasoner(report=_report("fallback"))

    reasoner = FallbackReasoner(primary=primary, fallback=fallback)
    reasoner.investigate(
        case_id="case-42",
        problem_description="My wifi keeps disconnecting.",
        plan=_plan(),
        evidence=[],
        research=[],
    )

    assert primary.was_called is True
    assert fallback.was_called is True
