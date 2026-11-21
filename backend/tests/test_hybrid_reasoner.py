from datetime import datetime, timezone

import pytest

from app.models.investigation_plan import InvestigationPlan
from app.models.investigation_report import Confidence, Hypothesis, InvestigationReport, Recommendation
from app.models.tool_result import ToolResult, ToolStatus
from app.reasoning.baseline_reasoner import BaselineReasoner
from app.reasoning.hybrid_reasoner import HybridReasoner


def ev(name, payload, status=ToolStatus.SUCCESS):
    return ToolResult(tool_name=name, status=status, collected_at=datetime.now(timezone.utc), payload=payload)


def plan():
    return InvestigationPlan(problem_description="p", tools_to_execute=["wifi"], matched_keywords=[],
                             created_at=datetime.now(timezone.utc))


def hyp(title, *evidence, confidence=Confidence.MEDIUM):
    return Hypothesis(title=title, explanation="e", supporting_evidence=list(evidence), confidence=confidence)


REC = Recommendation(title="AI step", reason="r", steps=["a", "b", "c"], expected_result="e", priority="medium")


class StubAI:
    """Stands in for a validated OllamaReasoner."""

    def __init__(self, hypotheses=(), recommendations=(), notes=(), error=None):
        self.hypotheses, self.recommendations, self.notes, self.error = list(hypotheses), list(recommendations), list(notes), error

    def investigate(self, case_id, problem_description, plan, evidence, research):
        if self.error:
            raise self.error
        return InvestigationReport(
            case_id=case_id, problem_description=problem_description, summary="AI PROSE MUST NOT APPEAR",
            hypotheses=self.hypotheses, evidence_used=evidence, recommendations=self.recommendations,
            confidence=Confidence.HIGH, reasoning_method="ollama:test", review_notes=self.notes,
            created_at=datetime.now(timezone.utc),
        )


def run(ai, evidence, complaint="my wifi is slow"):
    return HybridReasoner(BaselineReasoner(), ai).investigate("c1", complaint, plan(), evidence, [])


WEAK_WIFI = ev("wifi", {"connected": True, "signal_percent": 18, "link_speed_mbps": 150.0})
STOPPED_AUDIO = ev("audio", {"device_count": 1, "audio_service_status": "stopped",
                             "devices": [{"name": "Realtek", "status": "OK", "error_code": 0}]})


# ---- The floor: rule-based findings are never lost ---------------------------------

def test_a_rule_based_finding_survives_an_ai_that_says_nothing():
    report = run(StubAI(), [STOPPED_AUDIO], complaint="no sound")
    assert [h.title for h in report.hypotheses] == ["The Windows Audio service is not running"]
    assert report.confidence == Confidence.HIGH


def test_a_rule_based_finding_survives_an_ai_that_contradicts_it():
    ai = StubAI([hyp("Everything is fine", "Signal 99%")], notes=["x"])
    report = run(ai, [WEAK_WIFI])
    assert "Wi-Fi signal is weak" in [h.title for h in report.hypotheses]


def test_when_the_ai_is_unavailable_the_rule_based_report_is_returned_with_a_note():
    report = run(StubAI(error=ConnectionError("connection refused")), [WEAK_WIFI])

    assert [h.title for h in report.hypotheses] == ["Wi-Fi signal is weak"]
    assert report.reasoning_method == "deterministic_baseline"
    assert any("AI model could not be used" in n and "connection refused" in n for n in report.review_notes)


def test_any_exception_type_from_the_ai_is_contained():
    for error in (RuntimeError("x"), ValueError("y"), TimeoutError("z")):
        assert run(StubAI(error=error), [WEAK_WIFI]).hypotheses


# ---- What the AI may add ---------------------------------------------------------------

def test_ai_hypothesis_with_a_new_fact_is_added_with_its_recommendations():
    # 380 ms to connect is below every rule-based threshold, so only the AI notices it.
    network = ev("network", {"first_byte_ms": 400.0, "connect_ms": 380.0, "dns_ms": 10.0, "failed_samples": 0, "response_ok": True})
    ai = StubAI([hyp("Slow connection setup", "Connect time: 380 ms")], [REC])
    report = run(ai, [WEAK_WIFI, network])

    titles = [h.title for h in report.hypotheses]
    assert titles[0] == "Wi-Fi signal is weak"           # rule-based first
    assert "Slow connection setup" in titles
    assert REC in report.recommendations
    assert report.reasoning_method == "deterministic_baseline+ollama:test"


def test_an_ai_conclusion_about_a_fact_the_rules_already_flag_is_a_repeat():
    network = ev("network", {"first_byte_ms": 900.0, "dns_ms": 10.0, "failed_samples": 0, "response_ok": True})
    ai = StubAI([hyp("Congested network", "Time to first response: 900 ms")], [REC])
    report = run(ai, [network])

    assert [h.title for h in report.hypotheses] == ["Internet responses are slow"]
    assert REC not in report.recommendations


def test_ai_conclusion_that_repeats_a_rule_finding_is_left_out_with_a_note():
    ai = StubAI([hyp("Poor Wi-Fi reception", "Signal strength 18%")], [REC])  # same fact (18) as the rule
    report = run(ai, [WEAK_WIFI])

    assert [h.title for h in report.hypotheses] == ["Wi-Fi signal is weak"]
    assert REC not in report.recommendations               # its recommendations go with it
    assert any("repeated a rule-based finding" in n for n in report.review_notes)


def test_a_near_identical_title_is_also_a_repeat():
    ai = StubAI([hyp("Wi-Fi signal is weak", "Signal looks low")])
    assert len(run(ai, [WEAK_WIFI]).hypotheses) == 1


def test_the_ais_own_notes_are_kept():
    ai = StubAI(notes=['Removed an AI-suggested cause the collected evidence did not support: "X".'])
    assert any('"X"' in n for n in run(ai, [WEAK_WIFI]).review_notes)


# ---- The summary and confidence are never the model's words -----------------------------

def test_the_summary_is_rebuilt_from_verified_findings():
    report = run(StubAI(), [WEAK_WIFI])
    assert "AI PROSE MUST NOT APPEAR" not in report.summary
    assert "AI model whose suggestions were checked" in report.summary


def test_overall_confidence_is_derived_from_the_final_hypotheses_not_the_models_claim():
    ai = StubAI([hyp("Low thing", "Link rate 150 Mbps at 7 ms", confidence=Confidence.LOW)])
    healthy = ev("wifi", {"connected": True, "signal_percent": 90, "link_speed_mbps": 150.0})
    report = run(ai, [healthy])
    assert report.confidence == Confidence.LOW             # StubAI claimed HIGH


def test_no_findings_anywhere_gives_the_honest_no_finding_report():
    healthy = ev("wifi", {"connected": True, "signal_percent": 90, "link_speed_mbps": 300.0})
    report = run(StubAI(), [healthy], complaint="my laptop is slow")
    assert report.hypotheses == [] and report.confidence == Confidence.LOW
    assert "did not find a signal strong enough" in report.summary


# ---- The user's own case, end to end -----------------------------------------------------

USER_EVIDENCE = [
    ev("wifi", {"connected": True, "ssid": "VITC-HOS2-4", "signal_percent": 62, "link_speed_mbps": 200.0}),
    ev("network", {"attempted": 3, "successful": 3, "failed_samples": 0, "dns_ms": 2.8, "connect_ms": 4.6,
                   "first_byte_ms": 124.1, "response_ok": True}),
]


def test_not_working_complaint_with_healthy_evidence_says_it_could_not_be_reproduced():
    report = run(StubAI(), USER_EVIDENCE, complaint="my wifi is not working")

    assert report.hypotheses == []
    assert "could not reproduce a connection problem" in report.summary
    assert "62% signal" in report.summary and "124 ms" in report.summary
    assert "run Sherlock again while it is happening" in report.summary


def test_speed_complaint_with_healthy_evidence_explains_link_rate_instead():
    report = run(StubAI(), USER_EVIDENCE, complaint="my wifi speed is only 6 mbps")
    assert "not the speed of your internet connection" in report.summary
    assert "could not reproduce" not in report.summary


def test_no_not_reproduced_claim_when_the_internet_check_failed():
    evidence = [USER_EVIDENCE[0], ev("network", {"error": "timed out"}, ToolStatus.ERROR)]
    assert "could not reproduce" not in run(StubAI(), evidence, complaint="my wifi is not working").summary


def test_no_not_reproduced_claim_when_the_internet_check_looked_unhealthy():
    slow = ev("network", {"failed_samples": 0, "dns_ms": 2.8, "first_byte_ms": 1800.0, "response_ok": True})
    assert "could not reproduce" not in run(StubAI(), [USER_EVIDENCE[0], slow], complaint="my wifi is not working").summary


def test_no_not_reproduced_claim_for_a_captive_portal():
    portal = ev("network", {"failed_samples": 0, "dns_ms": 2.8, "first_byte_ms": 50.0, "response_ok": False})
    assert "could not reproduce" not in run(StubAI(), [USER_EVIDENCE[0], portal], complaint="my wifi is not working").summary


def test_no_not_reproduced_claim_when_some_checks_failed():
    flaky = ev("network", {"failed_samples": 1, "dns_ms": 2.8, "first_byte_ms": 50.0, "response_ok": True})
    assert "could not reproduce" not in run(StubAI(), [USER_EVIDENCE[0], flaky], complaint="my wifi is not working").summary


def test_no_not_reproduced_claim_for_a_complaint_that_is_not_about_the_connection():
    assert "could not reproduce" not in run(StubAI(), USER_EVIDENCE, complaint="my screen flickers").summary


# ---- Wiring ---------------------------------------------------------------------------------

def test_the_app_uses_the_hybrid_reasoner():
    from app.api.deps import get_reasoner

    assert isinstance(get_reasoner(), HybridReasoner)
