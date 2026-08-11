"""Tests for OllamaReasoner.

`httpx.post` is monkeypatched at the module boundary
(`ollama_reasoner.httpx.post`), same pattern used for `TavilyResearcher`
— no real network calls, no real Ollama instance required to run this
suite.
"""

import json
from datetime import datetime, timezone

import httpx
import pytest

from app.models.investigation_plan import InvestigationPlan
from app.models.investigation_report import Confidence
from app.models.research_result import ResearchResult
from app.models.tool_result import ToolResult, ToolStatus
from app.reasoning.ollama_reasoner import OllamaReasoner, OllamaReasoningError


class _FakeResponse:
    def __init__(self, json_body: object, status_code: int = 200) -> None:
        self._json_body = json_body
        self.status_code = status_code

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise httpx.HTTPStatusError("error", request=None, response=self)  # type: ignore[arg-type]

    def json(self) -> object:
        return self._json_body


def _chat_response(content: object) -> _FakeResponse:
    """An Ollama /api/chat-shaped response wrapping the given content
    (already-serialized JSON text, matching how Ollama actually returns
    it with format="json").
    """
    text = content if isinstance(content, str) else json.dumps(content)
    return _FakeResponse({"message": {"role": "assistant", "content": text}})


def _plan() -> InvestigationPlan:
    return InvestigationPlan(
        problem_description="My laptop becomes slow after startup.",
        tools_to_execute=["disk"],
        matched_keywords=["slow"],
        created_at=datetime.now(timezone.utc),
    )


def _reasoner() -> OllamaReasoner:
    return OllamaReasoner(base_url="http://localhost:11434", model="llama3.1", timeout_seconds=5.0)


_VALID_REPORT_JSON = {
    "summary": "One drive is critically low on free space.",
    "hypotheses": [
        {
            "title": "C: is low on free space",
            "explanation": "C: is using 92.5% of its capacity, which may be contributing to slowdowns.",
            "supporting_evidence": ["C: usage: 92.5%"],
            "contradicting_evidence": [],
            "confidence": "medium",
        }
    ],
    "recommendations": ["Consider freeing up space on C:."],
    "confidence": "medium",
}


def _disk_evidence() -> ToolResult:
    return ToolResult(
        tool_name="disk",
        status=ToolStatus.SUCCESS,
        collected_at=datetime.now(timezone.utc),
        payload={"volumes": [{"mountpoint": "C:\\", "usage_percent": 92.5, "free_gb": 12.86}]},
    )


# --- Successful call --------------------------------------------------


def test_successful_call_returns_a_well_formed_report(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "app.reasoning.ollama_reasoner.httpx.post", lambda *a, **k: _chat_response(_VALID_REPORT_JSON)
    )

    report = _reasoner().investigate(
        case_id="case-1",
        problem_description="My laptop becomes slow after startup.",
        plan=_plan(),
        evidence=[_disk_evidence()],
        research=[],
    )

    assert report.case_id == "case-1"
    assert report.summary == _VALID_REPORT_JSON["summary"]
    assert len(report.hypotheses) == 1
    assert report.hypotheses[0].title == "C: is low on free space"
    assert report.hypotheses[0].confidence == Confidence.MEDIUM
    assert report.recommendations == ["Consider freeing up space on C:."]
    assert report.confidence == Confidence.MEDIUM
    assert report.reasoning_method == "ollama:llama3.1"


def test_reasoning_method_includes_the_configured_model_name(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "app.reasoning.ollama_reasoner.httpx.post", lambda *a, **k: _chat_response(_VALID_REPORT_JSON)
    )

    reasoner = OllamaReasoner(base_url="http://localhost:11434", model="qwen2.5", timeout_seconds=5.0)
    report = reasoner.investigate(
        case_id="case-1",
        problem_description="Anything.",
        plan=_plan(),
        evidence=[],
        research=[],
    )

    assert report.reasoning_method == "ollama:qwen2.5"


def test_evidence_used_includes_all_evidence_even_failed_results(monkeypatch: pytest.MonkeyPatch) -> None:
    """evidence_used is attached directly from the inputs, not generated
    by the model — a failed tool result must still appear there even
    though it's excluded from the prompt (see the next test).
    """
    monkeypatch.setattr(
        "app.reasoning.ollama_reasoner.httpx.post", lambda *a, **k: _chat_response(_VALID_REPORT_JSON)
    )
    failed_result = ToolResult(
        tool_name="startup",
        status=ToolStatus.ERROR,
        collected_at=datetime.now(timezone.utc),
        payload={"error": "boom"},
    )
    evidence = [_disk_evidence(), failed_result]

    report = _reasoner().investigate(
        case_id="case-1", problem_description="Anything.", plan=_plan(), evidence=evidence, research=[]
    )

    assert report.evidence_used == evidence


def test_failed_evidence_is_excluded_from_the_prompt(monkeypatch: pytest.MonkeyPatch) -> None:
    captured_prompts: list[str] = []

    def _capture_and_respond(url: str, json: dict, **kwargs: object) -> _FakeResponse:
        user_message = next(m["content"] for m in json["messages"] if m["role"] == "user")
        captured_prompts.append(user_message)
        return _chat_response(_VALID_REPORT_JSON)

    monkeypatch.setattr("app.reasoning.ollama_reasoner.httpx.post", _capture_and_respond)

    failed_result = ToolResult(
        tool_name="startup",
        status=ToolStatus.ERROR,
        collected_at=datetime.now(timezone.utc),
        payload={"error": "boom"},
    )
    _reasoner().investigate(
        case_id="case-1",
        problem_description="Anything.",
        plan=_plan(),
        evidence=[_disk_evidence(), failed_result],
        research=[],
    )

    assert "startup" not in captured_prompts[0]
    assert "boom" not in captured_prompts[0]
    assert "92.5" in captured_prompts[0]


def test_research_sources_are_attached_directly_not_generated_by_the_model(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "app.reasoning.ollama_reasoner.httpx.post", lambda *a, **k: _chat_response(_VALID_REPORT_JSON)
    )
    research = [
        ResearchResult(
            title="Example",
            url="https://example.com",
            snippet="...",
            source="example.com",
            retrieved_at=datetime.now(timezone.utc),
        )
    ]

    report = _reasoner().investigate(
        case_id="case-1", problem_description="Anything.", plan=_plan(), evidence=[], research=research
    )

    assert report.research_sources == research
    assert report.research_notice is None


def test_no_research_produces_a_research_notice(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "app.reasoning.ollama_reasoner.httpx.post", lambda *a, **k: _chat_response(_VALID_REPORT_JSON)
    )

    report = _reasoner().investigate(
        case_id="case-1", problem_description="Anything.", plan=_plan(), evidence=[], research=[]
    )

    assert report.research_sources == []
    assert report.research_notice is not None


# --- Network / backend failures --------------------------------------


def test_connection_failure_raises_ollama_reasoning_error(monkeypatch: pytest.MonkeyPatch) -> None:
    def _raise_connection_error(*args: object, **kwargs: object) -> None:
        raise httpx.ConnectError("connection refused")

    monkeypatch.setattr("app.reasoning.ollama_reasoner.httpx.post", _raise_connection_error)

    with pytest.raises(OllamaReasoningError):
        _reasoner().investigate(
            case_id="case-1", problem_description="Anything.", plan=_plan(), evidence=[], research=[]
        )


def test_non_2xx_response_raises_ollama_reasoning_error(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "app.reasoning.ollama_reasoner.httpx.post",
        lambda *a, **k: _FakeResponse({"error": "model not found"}, status_code=404),
    )

    with pytest.raises(OllamaReasoningError):
        _reasoner().investigate(
            case_id="case-1", problem_description="Anything.", plan=_plan(), evidence=[], research=[]
        )


def test_response_missing_message_content_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "app.reasoning.ollama_reasoner.httpx.post", lambda *a, **k: _FakeResponse({"message": {}})
    )

    with pytest.raises(OllamaReasoningError):
        _reasoner().investigate(
            case_id="case-1", problem_description="Anything.", plan=_plan(), evidence=[], research=[]
        )


# --- Malformed model output --------------------------------------------


def test_non_json_content_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "app.reasoning.ollama_reasoner.httpx.post",
        lambda *a, **k: _chat_response("this is not JSON at all"),
    )

    with pytest.raises(OllamaReasoningError):
        _reasoner().investigate(
            case_id="case-1", problem_description="Anything.", plan=_plan(), evidence=[], research=[]
        )


def test_json_that_is_not_an_object_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "app.reasoning.ollama_reasoner.httpx.post", lambda *a, **k: _chat_response(["just", "a", "list"])
    )

    with pytest.raises(OllamaReasoningError):
        _reasoner().investigate(
            case_id="case-1", problem_description="Anything.", plan=_plan(), evidence=[], research=[]
        )


def test_missing_required_field_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    incomplete = {"summary": "ok", "hypotheses": [], "recommendations": []}  # missing "confidence"
    monkeypatch.setattr(
        "app.reasoning.ollama_reasoner.httpx.post", lambda *a, **k: _chat_response(incomplete)
    )

    with pytest.raises(OllamaReasoningError):
        _reasoner().investigate(
            case_id="case-1", problem_description="Anything.", plan=_plan(), evidence=[], research=[]
        )


def test_invalid_confidence_value_raises() -> None:
    """A confidence value outside low/medium/high must be rejected, not
    silently coerced — it's exactly the kind of fabricated precision
    the report model exists to prevent.
    """
    from app.reasoning.ollama_reasoner import _parse_report_body

    body = json.dumps(
        {"summary": "ok", "hypotheses": [], "recommendations": [], "confidence": "extremely high"}
    )

    with pytest.raises(OllamaReasoningError):
        _parse_report_body(body)


def test_hypothesis_missing_required_fields_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    malformed = {
        "summary": "ok",
        "hypotheses": [{"title": "Missing everything else"}],
        "recommendations": [],
        "confidence": "low",
    }
    monkeypatch.setattr(
        "app.reasoning.ollama_reasoner.httpx.post", lambda *a, **k: _chat_response(malformed)
    )

    with pytest.raises(OllamaReasoningError):
        _reasoner().investigate(
            case_id="case-1", problem_description="Anything.", plan=_plan(), evidence=[], research=[]
        )


def test_hypotheses_not_a_list_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    malformed = {"summary": "ok", "hypotheses": "not a list", "recommendations": [], "confidence": "low"}
    monkeypatch.setattr(
        "app.reasoning.ollama_reasoner.httpx.post", lambda *a, **k: _chat_response(malformed)
    )

    with pytest.raises(OllamaReasoningError):
        _reasoner().investigate(
            case_id="case-1", problem_description="Anything.", plan=_plan(), evidence=[], research=[]
        )
