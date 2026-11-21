"""Evidence grounding: check an AI model's claims against the real evidence.

Prompt rules do not bind a language model. A small local model told to
"only reference facts in the EVIDENCE" and to "return no hypotheses if the
evidence does not support one" will still produce a confident, plausible
cause (for example "network adapter or driver issues") for a Wi-Fi
connection whose measurements are all healthy. So the rule is enforced
here, in code, on the model's output.

A supporting-evidence entry is *grounded* only if it cites at least one
number and every number it cites appears in the collected evidence (to
the precision the entry states). A cause the model cannot back with a real
measurement is removed, however reasonable it sounds. This is deliberately
strict and one-sided: it can discard a true statement that the model failed
to quote with a number, but it cannot let an invented one through. The
rule-based checks (see `signals.py`) cover findings that are not numeric,
which is why the model is only ever allowed to add to them.

Only successfully collected evidence counts as a fact. A failed tool's
payload is an error message and grounds nothing.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Iterable

from app.models.investigation_report import Confidence, Hypothesis
from app.models.tool_result import ToolResult, ToolStatus

# A number not glued to a word or another number, so "AX201" or "802.11ac"
# do not yield stray figures from identifiers.
_NUMBER = re.compile(r"(?<![\w.])-?\d+(?:\.\d+)?(?![\w])")
_IDENTIFIER_WITH_DIGITS = re.compile(r"\b[\w.-]*\d[\w.-]*[A-Za-z][\w.-]*\b|\b[A-Za-z][\w.-]*\d[\w.-]*\b")


@dataclass(frozen=True)
class EvidenceFacts:
    """Every number the successfully collected evidence actually contains."""

    numbers: tuple[float, ...]
    strings: tuple[str, ...]


@dataclass(frozen=True)
class GroundingResult:
    kept: list[Hypothesis]
    dropped_titles: list[str]
    removed_entries: int


def collect_facts(evidence: Iterable[ToolResult]) -> EvidenceFacts:
    numbers: list[float] = []
    strings: list[str] = []
    for item in evidence:
        if item.status != ToolStatus.SUCCESS:
            continue
        _walk(item.payload, numbers, strings)
    return EvidenceFacts(tuple(numbers), tuple(strings))


def _walk(value: Any, numbers: list[float], strings: list[str]) -> None:
    if isinstance(value, bool) or value is None:
        return
    if isinstance(value, (int, float)):
        numbers.append(float(value))
    elif isinstance(value, str):
        strings.append(value.casefold())
    elif isinstance(value, dict):
        for child in value.values():
            _walk(child, numbers, strings)
    elif isinstance(value, (list, tuple)):
        numbers.append(float(len(value)))  # "2 volumes", "3 audio devices"
        for child in value:
            _walk(child, numbers, strings)


def is_grounded(entry: str, facts: EvidenceFacts) -> bool:
    """True if `entry` cites at least one number and all of them are real."""
    text = entry
    # Digits inside names the evidence itself contains ("Intel Wi-Fi 6 AX201",
    # "802.11ac") are labels, not claimed measurements.
    folded = text.casefold()
    for known in facts.strings:
        if len(known) >= 4 and any(ch.isdigit() for ch in known) and known in folded:
            text = re.sub(re.escape(known), " ", text, flags=re.IGNORECASE)
            folded = text.casefold()
    text = _IDENTIFIER_WITH_DIGITS.sub(" ", text)

    cited = _NUMBER.findall(text)
    if not cited:
        return False
    return all(_matches_some_fact(token, facts.numbers) for token in cited)


def _matches_some_fact(token: str, numbers: tuple[float, ...]) -> bool:
    value = float(token)
    decimals = len(token.split(".")[1]) if "." in token else 0
    tolerance = 0.5 * 10 ** (-decimals) + 1e-9  # the entry may round what the evidence holds precisely
    return any(abs(value - fact) <= tolerance for fact in numbers)


def ground_hypotheses(hypotheses: list[Hypothesis], facts: EvidenceFacts) -> GroundingResult:
    kept: list[Hypothesis] = []
    dropped: list[str] = []
    removed_entries = 0

    for hypothesis in hypotheses:
        grounded = [entry for entry in hypothesis.supporting_evidence if is_grounded(entry, facts)]
        removed_entries += len(hypothesis.supporting_evidence) - len(grounded)
        if not grounded:
            dropped.append(hypothesis.title)
            continue
        kept.append(hypothesis.model_copy(update={"supporting_evidence": grounded}))

    return GroundingResult(kept=kept, dropped_titles=dropped, removed_entries=removed_entries)


def overall_confidence(hypotheses: list[Hypothesis]) -> Confidence:
    """The strongest single hypothesis's confidence.

    Deliberately not an average (which would understate one genuinely strong
    finding) and not a count (which would overstate several weak ones). With
    no hypotheses there is nothing to be confident about, so it is LOW.
    """
    if any(h.confidence == Confidence.HIGH for h in hypotheses):
        return Confidence.HIGH
    if any(h.confidence == Confidence.MEDIUM for h in hypotheses):
        return Confidence.MEDIUM
    return Confidence.LOW
