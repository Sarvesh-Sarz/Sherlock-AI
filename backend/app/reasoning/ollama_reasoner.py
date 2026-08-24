"""OllamaReasoner — a local LLM-backed `Reasoner`.

Calls a locally-running Ollama (https://ollama.com) instance to produce
the interpretive parts of a report (summary, hypotheses,
recommendations, overall confidence). The parts that must never be
fabricated — `case_id`, `evidence_used`, `research_sources`,
`created_at` — are never asked of the model at all; they're attached
directly from this reasoner's own inputs after the model responds. The
model literally cannot invent a piece of evidence or a research
citation that wasn't already real, because it's never given the chance
to produce those fields.

Ollama runs entirely on the user's machine — no API key, no data
leaving it. This is deliberately one interchangeable implementation of
`Reasoner` (see `reasoner.py`), not a special case: a different local
runtime (AMD-optimized inference, another backend) would look the same
from everywhere else in the project.

Never raises silently and never guesses at malformed output — an
unreachable Ollama, a non-2xx response, or a response that doesn't
parse into the expected shape all raise `OllamaReasoningError`. That's
intentional: this reasoner is meant to be wrapped in `FallbackReasoner`
(see `fallback_reasoner.py`), which is what actually decides what to do
about a failure. Papering over a bad response here (e.g. returning a
best-effort partial report) would hide a real failure behind an
answer that looks fine but wasn't validated.
"""

import json
import logging
from datetime import datetime, timezone

import httpx
from pydantic import ValidationError

from app.models.investigation_plan import InvestigationPlan
from app.models.investigation_report import Confidence, Hypothesis, InvestigationReport
from app.models.research_result import ResearchResult
from app.models.tool_result import ToolResult, ToolStatus
from app.reasoning.reasoner import NO_RESEARCH_NOTICE, Reasoner
from app.models.investigation_report import (
    Confidence,
    Hypothesis,
    InvestigationReport,
    Recommendation,
)

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = """You are Sherlock AI's diagnostic reasoning assistant. You analyze Windows \
diagnostic evidence (and, if present, internet research) to identify PLAUSIBLE contributing \
factors to a problem the user reported about their own machine.

STRICT RULES — follow every one of these exactly:
1.You may ONLY reference facts that appear in the EVIDENCE or RESEARCH sections.
Never invent, assume, or infer a fact that isn't present in either section.
2. Never state a hypothesis as a confirmed fact. Always use hedged language: "may be", "could be \
contributing to", "is a plausible factor in". Never say a component "is failing", "is broken", \
"is caused by", or use similarly definitive language.
3. Every "supporting_evidence" entry must directly reference a real value
   from the EVIDENCE or RESEARCH sections — never fabricate a number,
   name, or detail.
4. If the evidence does not clearly support any hypothesis, return an empty "hypotheses" list. Do \
not invent a plausible-sounding cause just to have something to say.
5. Recommendations must be things the USER may look into or change manually. Never describe an \
action you took or will take. Never recommend deleting system files, disabling security software, \
or editing the registry.
6. Recommendations must be actionable for the USER, not generic advice.
7. Each recommendation must contain concrete steps that a Windows user can perform manually.
8. Prefer specific Windows UI paths when appropriate, such as:
   "Open Task Manager → Startup apps."
   Do not invent menu names or settings that are unrelated to the evidence.
9. Every recommendation must be grounded in the evidence or research provided.
10. Do not recommend an action merely because it is a common troubleshooting step if the evidence does not support it.
11. Never instruct the user to delete system files, disable security software, modify the registry, or perform destructive actions.
12. Keep recommendations ordered by priority: high, then medium, then low.
13. Steps should form a logical sequence. When possible, start with the
   safest and simplest check, then move to more advanced checks only if
   the previous step does not resolve the issue.

14. Include a verification step at the end so the user knows how to determine
   whether the problem was resolved.

15. Do not stop after directing the user to a Windows settings page. Tell
    the user what to look for and what to do there.
16.Start with the most common and least invasive troubleshooting steps.
Only suggest hardware cleaning or replacement after software and
configuration checks have been exhausted.
17.Each recommendation must contain between 3 and 6 concrete,
numbered troubleshooting steps.

Bad:
- Check the connection.

Good:
1. Disconnect the headphones.
2. Reconnect them firmly.
3. Try another port.
4. Verify the device appears in Windows Sound settings.
5. Play a test sound.

Recommendations should be detailed enough that a non-technical
user can follow them without needing to search online.
18. Respond with ONLY one JSON object, no text before or after it, matching exactly:
{
  "summary": "one or two sentence overview of what was found",
  "hypotheses": [
    {
      "title": "short title",
      "explanation": "hedged explanation referencing the evidence",
      "supporting_evidence": ["evidence-derived string", "..."],
      "contradicting_evidence": [],
      "confidence": "low" | "medium" | "high"
    }
  ],
  "recommendations": [
    {
        "title": "short action title",
        "reason": "why this action is relevant",
        "steps": [
            "specific step the user can perform",
            "next step based on the result",
            "another troubleshooting step",
            "final verification step"
        ],
        "expected_result": "what the user should expect",
        "priority": "high"
    }
    ]
  "confidence": "low" | "medium" | "high"
    Every recommendation MUST contain all five fields:
    title, reason, steps, expected_result, priority.

    priority MUST be exactly one of:
    "high", "medium", "low".

    Never omit priority.
    IMPORTANT:
    Before responding, verify that your JSON contains ALL of these top-level keys:
    "summary", "hypotheses", "recommendations", "confidence".

    The "confidence" key is mandatory even when there are no hypotheses or recommendations.

    If there are no hypotheses, use:
    "hypotheses": []

    If there are no recommendations, use:
    "recommendations": []

    Never omit "confidence".

    The final JSON MUST have this exact top-level structure:
    {
    "summary": "...",
    "hypotheses": [],
    "recommendations": [],
    "confidence": "low"
    }
}"""


class OllamaReasoningError(RuntimeError):
    """Raised when Ollama is unreachable or its response can't be used.

    A distinct type (rather than a bare RuntimeError) so a caller other
    than `FallbackReasoner` — a test, a future caller that wants to
    distinguish "no LLM available" from other failures — can catch this
    specifically if it needs to.
    """


class OllamaReasoner(Reasoner):
    """Calls a local Ollama instance's chat API to produce a report."""

    def __init__(self, base_url: str, model: str, timeout_seconds: float) -> None:
        self._base_url = base_url.rstrip("/")
        self._model = model
        self._timeout_seconds = timeout_seconds

    def investigate(
        self,
        case_id: str,
        problem_description: str,
        plan: InvestigationPlan,
        evidence: list[ToolResult],
        research: list[ResearchResult],
    ) -> InvestigationReport:
        # Only successfully-collected evidence is worth putting in the
        # prompt — a failed tool's payload is an error message, not a
        # fact to reason over (same restraint app.reasoning.signals
        # applies for the baseline reasoner). The full `evidence` list,
        # failures included, still ends up in the returned report's
        # `evidence_used` below — that's an observed fact regardless.
        successful_evidence = [result for result in evidence if result.status == ToolStatus.SUCCESS]
        user_prompt = _build_user_prompt(problem_description, successful_evidence, research)

        body = self._call_ollama(user_prompt)
        summary, hypotheses, recommendations, confidence = _parse_report_body(body)

        return InvestigationReport(
            case_id=case_id,
            problem_description=problem_description,
            summary=summary,
            hypotheses=hypotheses,
            evidence_used=evidence,
            recommendations=recommendations,
            confidence=confidence,
            research_sources=research,
            research_notice=None if research else NO_RESEARCH_NOTICE,
            reasoning_method=f"ollama:{self._model}",
            created_at=datetime.now(timezone.utc),
        )

    def _call_ollama(self, user_prompt: str) -> str:
        """POST to Ollama's chat API and return the raw message content."""
        try:
            response = httpx.post(
                f"{self._base_url}/api/chat",
                json={
                    "model": self._model,
                    "messages": [
                        {"role": "system", "content": _SYSTEM_PROMPT},
                        {"role": "user", "content": user_prompt},
                    ],
                    "format": {
                        "type": "object",
                        "properties": {
                            "summary": {
                                "type": "string"
                            },
                            "hypotheses": {
                                "type": "array",
                                "items": {
                                    "type": "object",
                                    "properties": {
                                        "title": {
                                            "type": "string"
                                        },
                                        "explanation": {
                                            "type": "string"
                                        },
                                        "supporting_evidence": {
                                            "type": "array",
                                            "items": {
                                                "type": "string"
                                            }
                                        },
                                        "contradicting_evidence": {
                                            "type": "array",
                                            "items": {
                                                "type": "string"
                                            }
                                        },
                                        "confidence": {
                                            "type": "string",
                                            "enum": ["low", "medium", "high"]
                                        },
                                    },
                                    "required": [
                                        "title",
                                        "explanation",
                                        "supporting_evidence",
                                        "contradicting_evidence",
                                        "confidence",
                                    ],
                                },
                            },
                            "recommendations": {
                                "type": "array",
                                "items": {
                                    "type": "object",
                                    "properties": {
                                        "title": {
                                            "type": "string"
                                        },
                                        "reason": {
                                            "type": "string"
                                        },
                                        "steps": {
                                            "type": "array",
                                            "items": {
                                                "type": "string"
                                            }
                                        },
                                        "expected_result": {
                                            "type": "string"
                                        },
                                        "priority": {
                                            "type": "string",
                                            "enum": ["high", "medium", "low"]
                                        },
                                    },
                                    "required": [
                                        "title",
                                        "reason",
                                        "steps",
                                        "expected_result",
                                        "priority",
                                    ],
                                },
                            },
                            "confidence": {
                                "type": "string",
                                "enum": ["low", "medium", "high"]
                            },
                        },
                        "required": [
                            "summary",
                            "hypotheses",
                            "recommendations",
                            "confidence",
                        ],
                    },
                    "stream": False,
                },
                timeout=self._timeout_seconds,
            )

            response.raise_for_status()
            body = response.json()

        except (httpx.HTTPError, ValueError) as exc:
            raise OllamaReasoningError(
                f"Could not reach Ollama at {self._base_url} "
                f"(model={self._model}): {exc}"
            ) from exc

        content = body.get("message", {}).get("content") if isinstance(body, dict) else None

        if not isinstance(content, str) or not content:
            raise OllamaReasoningError(
                "Ollama's response did not include message.content."
            )

        return content

def _parse_report_body(
    raw_text: str,
) -> tuple[str, list[Hypothesis], list[Recommendation], Confidence]:
    """Parse and validate the model's JSON text into report fields.

    Deliberately strict: a response that doesn't parse as JSON, isn't
    an object, or is missing/mistyped fields raises rather than being
    coerced into something plausible-looking. Pydantic validates each
    hypothesis (including that `confidence` is one of the three real
    values) the same way it would validate any other input to this
    project — this isn't hand-rolled validation logic distinct from how
    the rest of the app handles untrusted input.
    """
    try:
        parsed = json.loads(raw_text)
    except json.JSONDecodeError as exc:
        raise OllamaReasoningError(f"Ollama did not return valid JSON: {exc}") from exc

    if not isinstance(parsed, dict):
        raise OllamaReasoningError("Ollama's JSON response was not an object.")

    hypotheses_raw = parsed.get("hypotheses")
    if not isinstance(hypotheses_raw, list):
        raise OllamaReasoningError("Ollama's response did not include a 'hypotheses' list.")

    recommendations_raw = parsed.get("recommendations")
    if not isinstance(recommendations_raw, list):
        raise OllamaReasoningError("Ollama's response did not include a 'recommendations' list.")

    try:
        hypotheses = [Hypothesis(**item) for item in hypotheses_raw]
        summary = str(parsed["summary"])
        recommendations = [
            Recommendation(**item)
            for item in recommendations_raw
        ]
        confidence = Confidence(parsed["confidence"])
    except (KeyError, TypeError, ValueError, ValidationError) as exc:
        raise OllamaReasoningError(f"Ollama's response did not match the expected report shape: {exc}") from exc

    return summary, hypotheses, recommendations, confidence


def _build_user_prompt(
    problem_description: str, evidence: list[ToolResult], research: list[ResearchResult]
) -> str:
    return (
        f'PROBLEM REPORTED BY THE USER:\n"{problem_description}"\n\n'
        "EVIDENCE (the only facts you may reference — nothing outside this section is real):\n"
        f"{_format_evidence(evidence)}\n\n"
        "RESEARCH (optional supporting context; may be empty):\n"
        f"{_format_research(research)}\n\n"
        "Respond with a single JSON object matching the schema in your instructions. "
        "No text outside the JSON."
    )


def _format_evidence(evidence: list[ToolResult]) -> str:
    if not evidence:
        return "(No evidence was successfully collected.)"
    return "\n".join(f"- {result.tool_name}: {json.dumps(result.payload)}" for result in evidence)


def _format_research(research: list[ResearchResult]) -> str:
    if not research:
        return "(No external research is available.)"

    return "\n".join(
        f"- {item.title}: {item.snippet[:500]}"
        for item in research[:3]
    )