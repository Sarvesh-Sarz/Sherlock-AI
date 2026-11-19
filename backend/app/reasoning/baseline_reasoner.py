"""BaselineReasoner — the deterministic, rule-based `Reasoner`.

Not an LLM, and doesn't pretend to be one. Every hypothesis it produces
comes from `app.reasoning.signals.detect_signals`'s fixed threshold
rules over real evidence values — nothing here is generated,
paraphrased, or inferred beyond formatting a number into a sentence.
That's what makes every claim traceable by construction: a supporting-
evidence string is built directly from a real field on a real
`ToolResult`, so there's no step where something could be invented.

This is deliberately the "smallest useful" reasoning implementation
(see the project's model-strategy requirement) — it exists to give
`Reasoner`'s contract a real, working, fully-tested implementation
today, and to make swapping in a local-LLM-backed `Reasoner` later a
matter of implementing the same interface, not restructuring anything
that calls it.
"""

import re
from collections.abc import Iterable
from datetime import datetime, timezone

from app.models.investigation_plan import InvestigationPlan
from app.models.investigation_report import (
    Confidence,
    Hypothesis,
    InvestigationReport,
    Recommendation,
)
from app.models.research_result import ResearchResult
from app.models.tool_result import ToolResult, ToolStatus
from app.reasoning.reasoner import NO_RESEARCH_NOTICE, Reasoner
from app.reasoning.signals import Signal, detect_signals

REASONING_METHOD = "deterministic_baseline"


class BaselineReasoner(Reasoner):
    """Deterministic, rule-based `Reasoner`.

    Never raises in practice: its own logic is pure and operates only
    on already-validated evidence, so there's no external failure mode
    to guard against the way a future LLM-backed reasoner would need to
    (see `Reasoner.investigate`'s docstring on why the interface still
    permits raising).
    """

    def investigate(
        self,
        case_id: str,
        problem_description: str,
        plan: InvestigationPlan,
        evidence: list[ToolResult],
        research: list[ResearchResult],
    ) -> InvestigationReport:
        signals = detect_signals(evidence)
        hypotheses = [_hypothesis_from_signal(signal) for signal in signals]

        return InvestigationReport(
            case_id=case_id,
            problem_description=problem_description,
            summary=_build_summary(problem_description, hypotheses, evidence),
            hypotheses=hypotheses,
            evidence_used=evidence,
            recommendations=_recommendations_from_signals(signals),
            confidence=_overall_confidence(hypotheses),
            research_sources=research,
            research_notice=None if research else NO_RESEARCH_NOTICE,
            reasoning_method=REASONING_METHOD,
            created_at=datetime.now(timezone.utc),
        )


def _hypothesis_from_signal(signal: Signal) -> Hypothesis:
    return Hypothesis(
        title=signal.title,
        explanation=signal.explanation,
        supporting_evidence=signal.supporting_evidence,
        contradicting_evidence=[],
        confidence=signal.confidence,
    )


def _overall_confidence(hypotheses: list[Hypothesis]) -> Confidence:
    """The report's overall confidence is the strongest single
    hypothesis's confidence — deliberately not an average (which would
    understate one genuinely strong signal) or a count-based score
    (which would overstate several weak signals combined).
    """
    if any(h.confidence == Confidence.HIGH for h in hypotheses):
        return Confidence.HIGH
    if any(h.confidence == Confidence.MEDIUM for h in hypotheses):
        return Confidence.MEDIUM
    return Confidence.LOW


def _build_summary(
    problem_description: str,
    hypotheses: list[Hypothesis],
    evidence: list[ToolResult] | None = None,
) -> str:
    note = _healthy_wifi_note(problem_description, evidence or [])

    if not hypotheses:
        return (
            f'Sherlock reviewed the evidence collected for "{problem_description}" and did not '
            "find a signal strong enough to flag as a likely contributing factor, based on its "
            "current baseline (non-AI) rule set. This does not rule out a cause outside what the "
            "current diagnostic tools check." + note
        )

    factor_word = "factor" if len(hypotheses) == 1 else "factors"
    return (
        f'Sherlock reviewed the evidence collected for "{problem_description}" and identified '
        f"{len(hypotheses)} possible contributing {factor_word}, listed below with their "
        "supporting evidence. This is a baseline, rule-based analysis — no AI reasoning model is "
        "currently configured." + note
    )


_INTERNET_COMPLAINT = re.compile(r"\b(wi-?fi|wireless|internet|network|online|browsing)\b", re.IGNORECASE)


def _healthy_wifi_note(problem_description: str, evidence: list[ToolResult]) -> str:
    """Explain the common case of a healthy Wi-Fi link with a slow internet complaint.

    Link rate is the radio speed between this PC and the router; it is not
    the speed of the internet connection. Only added when the complaint is
    about the connection AND the Wi-Fi reading was real and healthy, so it
    never reassures on the basis of a failed or missing measurement.
    """
    if not _INTERNET_COMPLAINT.search(problem_description):
        return ""

    for item in evidence:
        if item.tool_name != "wifi" or item.status != ToolStatus.SUCCESS:
            continue
        payload = item.payload
        signal = payload.get("signal_percent")
        speed = payload.get("link_speed_mbps")
        if (
            payload.get("connected") is True
            and isinstance(signal, (int, float)) and not isinstance(signal, bool)
            and isinstance(speed, (int, float)) and not isinstance(speed, bool)
            and signal >= 40
            and speed >= 50
        ):
            return (
                f" The Wi-Fi link itself looked healthy ({signal:.0f}% signal, {speed:g} Mbps link "
                "rate). Link rate is the speed between this PC and the router, not the speed of "
                "your internet connection, so a slowdown may come from beyond the Wi-Fi link, such "
                "as the network's internet service or its limits."
            )
    return ""


def _recommendations_from_signals(signals: list[Signal]) -> list[Recommendation]:
    recommendations: list[Recommendation] = []
    seen: set[str] = set()

    for signal in signals:
        if signal.recommendation in seen:
            continue

        seen.add(signal.recommendation)

        recommendations.append(
            Recommendation(
                title=signal.recommendation,
                reason=signal.explanation,
                steps=[signal.recommendation],
                expected_result="This should help reduce or resolve the contributing factor.",
                priority="medium",
            )
        )

    return recommendations
