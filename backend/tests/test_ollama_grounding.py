"""OllamaReasoner against a model that makes things up.

Reproduces a real failure: with a perfectly healthy Wi-Fi connection, a small
local model reported "network adapter settings or driver issues". The
evidence below is that machine's actual evidence.
"""

import json
from datetime import datetime, timezone

import pytest

from app.models.investigation_plan import InvestigationPlan
from app.models.investigation_report import Confidence
from app.models.tool_result import ToolResult, ToolStatus
from app.reasoning.ollama_reasoner import OllamaReasoner


class FakeResponse:
    status_code = 200

    def __init__(self, body):
        self._body = body

    def raise_for_status(self):
        pass

    def json(self):
        return self._body


def model_says(monkeypatch, content):
    monkeypatch.setattr(
        "app.reasoning.ollama_reasoner.httpx.post",
        lambda *a, **k: FakeResponse({"message": {"role": "assistant", "content": json.dumps(content)}}),
    )


def ev(name, payload, status=ToolStatus.SUCCESS):
    return ToolResult(tool_name=name, status=status, collected_at=datetime.now(timezone.utc), payload=payload)


HEALTHY = [
    ev("wifi", {"connected": True, "ssid": "VITC-HOS2-4", "signal_percent": 62, "link_speed_mbps": 200.0,
                "interface": "Wi-Fi", "radio_type": "802.11ac", "authentication": "WPA2-Enterprise"}),
    ev("network", {"attempted": 3, "successful": 3, "failed_samples": 0, "dns_ms": 2.8, "connect_ms": 4.6,
                   "first_byte_ms": 124.1, "response_ok": True}),
]

REC = {
    "title": "Update the network driver", "reason": "r", "expected_result": "e", "priority": "high",
    "steps": ["Open Device Manager.", "Expand Network adapters.", "Update the driver.", "Test the connection."],
}
HALLUCINATION = {
    "summary": "The problem is likely related to network adapter settings or driver issues.",
    "hypotheses": [{
        "title": "Network adapter or driver problem",
        "explanation": "The adapter may be misconfigured.",
        "supporting_evidence": ["The Wi-Fi adapter settings may be incorrect", "Driver is outdated"],
        "contradicting_evidence": [],
        "confidence": "high",
    }],
    "recommendations": [REC],
    "confidence": "high",
}


def investigate(evidence=HEALTHY):
    plan = InvestigationPlan(problem_description="my wifi is not working", tools_to_execute=["wifi"],
                             matched_keywords=["wifi"], created_at=datetime.now(timezone.utc))
    return OllamaReasoner("http://localhost:11434", "qwen2.5:1.5b", 5.0).investigate(
        "c1", "my wifi is not working", plan, evidence, [])


def test_an_invented_cause_for_a_healthy_connection_is_removed(monkeypatch):
    model_says(monkeypatch, HALLUCINATION)
    report = investigate()

    assert report.hypotheses == []
    assert "driver issues" not in report.summary                  # the model's prose is not shown
    assert "did not propose any cause that the collected evidence supports" in report.summary
    assert report.recommendations == []                           # nothing left that they could support
    assert report.confidence == Confidence.LOW                    # not the model's claimed "high"


def test_the_report_says_what_was_removed_and_why(monkeypatch):
    model_says(monkeypatch, HALLUCINATION)
    notes = investigate().review_notes

    assert any("Network adapter or driver problem" in n and "did not support" in n for n in notes)
    assert any("recommendations" in n for n in notes)


def test_a_model_that_correctly_finds_nothing_is_left_alone(monkeypatch):
    model_says(monkeypatch, {"summary": "Nothing stands out.", "hypotheses": [], "recommendations": [], "confidence": "low"})
    report = investigate()

    assert report.hypotheses == [] and report.review_notes == []


def test_a_supported_hypothesis_survives_and_an_invented_one_beside_it_does_not(monkeypatch):
    content = {
        "summary": "Responses are slow.",
        "hypotheses": [
            {"title": "Slow responses", "explanation": "e", "supporting_evidence": ["First response took 124 ms"],
             "contradicting_evidence": [], "confidence": "medium"},
            HALLUCINATION["hypotheses"][0],
        ],
        "recommendations": [REC],
        "confidence": "high",
    }
    model_says(monkeypatch, content)
    report = investigate()

    assert [h.title for h in report.hypotheses] == ["Slow responses"]
    assert len(report.recommendations) == 1                       # kept: a supported cause remains
    assert report.confidence == Confidence.MEDIUM                  # from the surviving hypothesis, not the model's "high"
    assert report.summary == "Responses are slow."
    assert len(report.review_notes) == 1


def test_confidence_comes_from_the_evidence_backed_hypotheses_only(monkeypatch):
    content = {**HALLUCINATION, "hypotheses": [
        {"title": "Fast link", "explanation": "e", "supporting_evidence": ["Link rate 200 Mbps"],
         "contradicting_evidence": [], "confidence": "low"}], "confidence": "high"}
    model_says(monkeypatch, content)
    assert investigate().confidence == Confidence.LOW


def test_evidence_that_failed_cannot_back_a_cause(monkeypatch):
    model_says(monkeypatch, {"summary": "s", "hypotheses": [
        {"title": "Weak signal", "explanation": "e", "supporting_evidence": ["Signal 18%"],
         "contradicting_evidence": [], "confidence": "high"}], "recommendations": [], "confidence": "high"})
    failed = [ev("wifi", {"signal_percent": 18}, ToolStatus.ERROR)]

    assert investigate(failed).hypotheses == []
