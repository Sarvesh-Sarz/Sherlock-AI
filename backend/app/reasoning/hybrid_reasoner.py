"""HybridReasoner: rule-based findings are the floor; the AI model can only add.

Why this exists. The rule-based checks (see `signals.py`) are deterministic
and exact, but they only know what they were written to look for. A local
language model can notice more, but a small one also invents causes the
evidence does not support (see `grounding.py`). Using either alone loses
something:

- AI alone would let a weak model hide an obvious fault, such as a stopped
  Windows Audio service, simply by not mentioning it.
- Rules alone ignore everything the model could usefully add.

So the rule-based report is always built first and is never altered or
dropped. The AI's output is then checked against the evidence (inside
`OllamaReasoner`) and only what survives is added. The summary and the
overall confidence are rebuilt from the final hypotheses, never copied from
the model's own prose.

If the AI cannot be used at all (Ollama is down, the model is not pulled, the
reply is malformed) the rule-based report is returned with a note saying so.
Sherlock still works with no model available.
"""

import logging
import re

from app.models.investigation_plan import InvestigationPlan
from app.models.investigation_report import Hypothesis, InvestigationReport
from app.models.research_result import ResearchResult
from app.models.tool_result import ToolResult
from app.reasoning.baseline_reasoner import build_summary
from app.reasoning.grounding import overall_confidence
from app.reasoning.reasoner import Reasoner

logger = logging.getLogger(__name__)

_NUMBER = re.compile(r"(?<![\w.])-?\d+(?:\.\d+)?(?![\w])")
_WORDS = re.compile(r"[a-z]{3,}")


class HybridReasoner(Reasoner):
    def __init__(self, rules: Reasoner, ai: Reasoner) -> None:
        self._rules = rules
        self._ai = ai

    def investigate(
        self,
        case_id: str,
        problem_description: str,
        plan: InvestigationPlan,
        evidence: list[ToolResult],
        research: list[ResearchResult],
    ) -> InvestigationReport:
        base = self._rules.investigate(case_id, problem_description, plan, evidence, research)

        try:
            ai_report = self._ai.investigate(case_id, problem_description, plan, evidence, research)
        except Exception as exc:  # noqa: BLE001 - any AI failure must leave the rule-based report intact
            logger.warning("AI reasoning unavailable for case %s: %s", case_id, exc)
            return base.model_copy(
                update={
                    "review_notes": [
                        *base.review_notes,
                        f"The AI model could not be used ({_short(exc)}), so this report uses "
                        "rule-based checks only.",
                    ]
                }
            )

        additions = [h for h in ai_report.hypotheses if not _repeats_a_finding(h, base.hypotheses)]
        repeated = len(ai_report.hypotheses) - len(additions)

        notes = list(ai_report.review_notes)
        if repeated:
            noun = "conclusion" if repeated == 1 else "conclusions"
            notes.append(f"Left out {repeated} AI {noun} that repeated a rule-based finding.")

        hypotheses = [*base.hypotheses, *additions]

        # AI recommendations are only meaningful next to an AI cause that
        # survived; if the AI added nothing new, the rule-based ones stand alone.
        recommendations = [*base.recommendations, *(ai_report.recommendations if additions else [])]

        return base.model_copy(
            update={
                "summary": build_summary(problem_description, hypotheses, evidence, analysis="rules_and_ai"),
                "hypotheses": hypotheses,
                "recommendations": recommendations,
                "confidence": overall_confidence(hypotheses),
                "reasoning_method": f"{base.reasoning_method}+{ai_report.reasoning_method}",
                "review_notes": notes,
            }
        )


def _repeats_a_finding(candidate: Hypothesis, existing: list[Hypothesis]) -> bool:
    """True if `candidate` says what a rule-based finding already says.

    Same fact (they cite a common number) or nearly the same title. The
    rule-based version always wins, since it is the exact one.
    """
    candidate_numbers = _numbers(candidate.supporting_evidence)
    candidate_words = set(_WORDS.findall(candidate.title.casefold()))
    for known in existing:
        if candidate_numbers & _numbers(known.supporting_evidence):
            return True
        known_words = set(_WORDS.findall(known.title.casefold()))
        union = candidate_words | known_words
        if union and len(candidate_words & known_words) / len(union) >= 0.5:
            return True
    return False


def _numbers(entries: list[str]) -> set[float]:
    return {float(token) for entry in entries for token in _NUMBER.findall(entry)}


def _short(exc: Exception, limit: int = 120) -> str:
    text = str(exc) or exc.__class__.__name__
    return text if len(text) <= limit else text[: limit - 3] + "..."
