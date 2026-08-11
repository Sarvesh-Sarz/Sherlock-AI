"""Deterministic evidence interpretation, shared by hypothesis
generation and research-query construction.

A `Signal` is one deterministic observation worth investigating
further, derived from a single piece of evidence via a fixed threshold
rule — e.g. "a disk volume is over 85% full." `detect_signals` is the
one place "what counts as low disk space" (or high memory usage, or too
many startup entries) is defined; both `app.reasoning.baseline_reasoner`
(turns signals into hypotheses) and `app.reasoning.query_builder` (turns
signals into research queries) read from it, so the two can never
disagree about what evidence is worth acting on.

Purely internal to the reasoning package — not part of the API, and not
a domain model (see `app.models.investigation_report` for the
public-facing shapes this eventually feeds into).

Deliberately simple threshold rules, not scoring or ML: this is the
"smallest useful" deterministic baseline, not an attempt at the eventual
AI reasoning model.
"""

from dataclasses import dataclass

from app.models.investigation_report import Confidence
from app.models.tool_result import ToolResult, ToolStatus

_DISK_HIGH_USAGE_PERCENT = 85.0
_DISK_CRITICAL_USAGE_PERCENT = 95.0
_MEMORY_HIGH_USAGE_PERCENT = 85.0
_STARTUP_HIGH_ENTRY_COUNT = 10


@dataclass
class Signal:
    """One deterministic, evidence-backed observation."""

    title: str
    explanation: str
    supporting_evidence: list[str]
    confidence: Confidence
    research_query: str
    recommendation: str


def detect_signals(evidence: list[ToolResult]) -> list[Signal]:
    """Derive signals from whatever evidence was actually collected.

    Only evidence with `status == SUCCESS` is considered — a tool that
    failed to collect anything has nothing to reason over, and doing so
    would mean inferring from data that was never actually observed.

    CPU is deliberately never turned into a signal: `app.tools.cpu`
    measures utilization over a ~0.1s window (see its own docstring), a
    single instantaneous snapshot, not sustained monitoring. Treating
    that as evidence of a persistent problem would overstate what was
    actually observed — the CPU snapshot is still included in a
    report's `evidence_used` as an observed fact, it just never becomes
    a hypothesis on its own here.
    """
    signals: list[Signal] = []
    for result in evidence:
        if result.status != ToolStatus.SUCCESS:
            continue

        if result.tool_name == "disk":
            signals.extend(_disk_signals(result))
        elif result.tool_name == "memory":
            signal = _memory_signal(result)
            if signal is not None:
                signals.append(signal)
        elif result.tool_name == "startup":
            signal = _startup_signal(result)
            if signal is not None:
                signals.append(signal)

    return signals


def _disk_signals(result: ToolResult) -> list[Signal]:
    volumes = result.payload.get("volumes")
    if not isinstance(volumes, list):
        return []

    signals: list[Signal] = []
    for volume in volumes:
        if not isinstance(volume, dict):
            continue
        usage_percent = volume.get("usage_percent")
        if not isinstance(usage_percent, (int, float)) or usage_percent < _DISK_HIGH_USAGE_PERCENT:
            continue

        mountpoint = volume.get("mountpoint")
        mountpoint_label = mountpoint if isinstance(mountpoint, str) and mountpoint else "A local volume"
        free_gb = volume.get("free_gb")
        free_text = f", leaving {free_gb:.2f} GB free" if isinstance(free_gb, (int, float)) else ""
        is_critical = usage_percent >= _DISK_CRITICAL_USAGE_PERCENT

        signals.append(
            Signal(
                title=(
                    f"{mountpoint_label} is critically low on free space"
                    if is_critical
                    else f"{mountpoint_label} is running low on free space"
                ),
                explanation=(
                    f"{mountpoint_label} is using {usage_percent:.1f}% of its capacity{free_text}. "
                    "Very low free space on a system drive is a plausible contributing factor to "
                    "general slowdowns in Windows."
                ),
                supporting_evidence=[f"{mountpoint_label} usage: {usage_percent:.1f}%{free_text}."],
                confidence=Confidence.HIGH if is_critical else Confidence.MEDIUM,
                research_query="Windows low disk space performance impact",
                recommendation=(
                    f"Consider freeing up space on {mountpoint_label} "
                    "(for example, Disk Cleanup, or removing unused files or applications)."
                ),
            )
        )
    return signals


def _memory_signal(result: ToolResult) -> Signal | None:
    usage_percent = result.payload.get("usage_percent")
    if not isinstance(usage_percent, (int, float)) or usage_percent < _MEMORY_HIGH_USAGE_PERCENT:
        return None

    return Signal(
        title="High memory utilization",
        explanation=(
            f"System memory is at {usage_percent:.1f}% utilization at the time of measurement. "
            "Sustained high memory usage is a plausible contributing factor to slower application "
            "performance."
        ),
        supporting_evidence=[f"Memory usage: {usage_percent:.1f}%."],
        confidence=Confidence.HIGH if usage_percent >= 95 else Confidence.MEDIUM,
        research_query="Windows high memory usage performance impact",
        recommendation="Consider reviewing which applications are running and closing ones not in use.",
    )


def _startup_signal(result: ToolResult) -> Signal | None:
    total_entries = result.payload.get("total_entries")
    if not isinstance(total_entries, int) or total_entries < _STARTUP_HIGH_ENTRY_COUNT:
        return None

    return Signal(
        title="High number of startup entries",
        explanation=(
            f"{total_entries} programs are configured to start automatically at sign-in. A large "
            "number of startup entries is a plausible contributing factor to a slower startup."
        ),
        supporting_evidence=[f"{total_entries} startup entries detected."],
        confidence=Confidence.MEDIUM,
        research_query="Windows startup applications slow boot performance",
        recommendation=(
            "Consider reviewing Startup apps in Task Manager and disabling ones you don't need "
            "at every sign-in."
        ),
    )
