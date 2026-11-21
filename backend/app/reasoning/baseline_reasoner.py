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
from app.reasoning.grounding import overall_confidence
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
            summary=build_summary(problem_description, hypotheses, evidence),
            hypotheses=hypotheses,
            evidence_used=evidence,
            recommendations=_recommendations_from_signals(signals),
            confidence=overall_confidence(hypotheses),
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


def build_summary(
    problem_description: str,
    hypotheses: list[Hypothesis],
    evidence: list[ToolResult] | None = None,
    analysis: str = "rules",
) -> str:
    """The report summary, built from verified facts only.

    `analysis` says what produced the hypotheses: "rules" (the rule-based
    checks alone) or "rules_and_ai" (rule-based checks plus an AI model whose
    suggestions were checked against the evidence). It only changes the
    wording of what was done; never what was found.
    """
    note = _connection_note(problem_description, evidence or [])
    ai_assisted = analysis == "rules_and_ai"

    if not hypotheses:
        basis = (
            "either its rule-based checks or an AI model whose suggestions were checked against the "
            "collected evidence"
            if ai_assisted
            else "its current baseline (non-AI) rule set"
        )
        return (
            f'Sherlock reviewed the evidence collected for "{problem_description}" and did not '
            f"find a signal strong enough to flag as a likely contributing factor, based on {basis}. "
            "This does not rule out a cause outside what the current diagnostic tools check." + note
        )

    factor_word = "factor" if len(hypotheses) == 1 else "factors"
    method = (
        "Findings come from Sherlock's rule-based checks plus an AI model whose suggestions were "
        "checked against the collected evidence."
        if ai_assisted
        else "This is a baseline, rule-based analysis — no AI reasoning model is currently configured."
    )
    return (
        f'Sherlock reviewed the evidence collected for "{problem_description}" and identified '
        f"{len(hypotheses)} possible contributing {factor_word}, listed below with their "
        f"supporting evidence. {method}" + note
    )


_INTERNET_COMPLAINT = re.compile(r"\b(wi-?fi|wireless|internet|network|online|browsing)\b", re.IGNORECASE)
_SPEED_COMPLAINT = re.compile(r"\b(slow|speed|mbps|lag|laggy|buffering|latency)\b", re.IGNORECASE)

_WIFI_HEALTHY_SIGNAL_PERCENT = 40
_WIFI_HEALTHY_LINK_MBPS = 50
_NETWORK_HEALTHY_RESPONSE_MS = 500
_NETWORK_HEALTHY_DNS_MS = 300


def _number(value: object) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return float(value)


def _healthy_wifi(evidence: list[ToolResult]) -> tuple[float, float] | None:
    """(signal %, link Mbps) if there is a real, successful, healthy Wi-Fi reading."""
    for item in evidence:
        if item.tool_name != "wifi" or item.status != ToolStatus.SUCCESS:
            continue
        payload = item.payload
        signal, speed = _number(payload.get("signal_percent")), _number(payload.get("link_speed_mbps"))
        if (
            payload.get("connected") is True
            and signal is not None and signal >= _WIFI_HEALTHY_SIGNAL_PERCENT
            and speed is not None and speed >= _WIFI_HEALTHY_LINK_MBPS
        ):
            return signal, speed
    return None


def _healthy_network_response_ms(evidence: list[ToolResult]) -> float | None:
    """First-response time if the internet check succeeded and looked healthy."""
    for item in evidence:
        if item.tool_name != "network" or item.status != ToolStatus.SUCCESS:
            continue
        payload = item.payload
        response, dns = _number(payload.get("first_byte_ms")), _number(payload.get("dns_ms"))
        failed = _number(payload.get("failed_samples")) or 0
        if (
            payload.get("response_ok") is True
            and failed == 0
            and response is not None and response < _NETWORK_HEALTHY_RESPONSE_MS
            and dns is not None and dns < _NETWORK_HEALTHY_DNS_MS
        ):
            return response
    return None


def _connection_note(problem_description: str, evidence: list[ToolResult]) -> str:
    """Say what healthy connection evidence does and does not show.

    Only used for connection complaints, and only when the readings were
    real, successful and healthy, so it never reassures on the basis of a
    failed or missing measurement.

    - Speed complaint: link rate is the speed between this PC and the
      router, not the internet speed, so the slowdown may be beyond the link.
    - Anything else ("not working", "keeps dropping"): Sherlock could not
      reproduce the problem. A snapshot cannot catch an intermittent fault,
      and the report says so rather than inventing a cause.
    """
    if not _INTERNET_COMPLAINT.search(problem_description):
        return ""

    wifi = _healthy_wifi(evidence)
    if wifi is None:
        return ""
    signal, speed = wifi

    if _SPEED_COMPLAINT.search(problem_description):
        return (
            f" The Wi-Fi link itself looked healthy ({signal:.0f}% signal, {speed:g} Mbps link "
            "rate). Link rate is the speed between this PC and the router, not the speed of "
            "your internet connection, so a slowdown may come from beyond the Wi-Fi link, such "
            "as the network's internet service or its limits."
        )

    response = _healthy_network_response_ms(evidence)
    if response is None:
        return ""
    return (
        f" Sherlock could not reproduce a connection problem: Wi-Fi was connected ({signal:.0f}% "
        f"signal) and the internet check succeeded (first response in {response:.0f} ms). If the "
        "problem comes and goes, run Sherlock again while it is happening."
    )


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
