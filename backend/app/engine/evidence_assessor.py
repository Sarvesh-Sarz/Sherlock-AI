"""Conservative, deterministic follow-up decisions from structured evidence.

The Planner owns "complaint -> tools". This assessor owns only
"evidence -> follow-up tools": it looks at what the diagnostics actually
measured and decides whether another tool is worth running. It never
re-derives tools from the complaint text, so it cannot undo a deliberate
Planner decision (e.g. "wifi is slow" intentionally skips the broad
CPU/memory/startup scan).

Rules read the *real* payload contracts of the tools:

    cpu     {"usage_percent", "current_frequency", "max_frequency", ...}
    memory  {"usage_percent", "available_gb", "total_gb", ...}
    disk    {"volumes": [{"mountpoint", "usage_percent", "free_gb", ...}]}

Principles (see project notes):
- Failed or non-success evidence is *unknown*, never "normal" and never a trigger.
- Missing, malformed, or out-of-range readings are ignored, not guessed.
- A tool already executed in this run is never recommended again.
- Every recommendation carries a human-readable reason.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Iterable

from app.models.tool_result import ToolResult

# Thresholds are module constants so they are visible, tunable, and testable.
CPU_HIGH_PERCENT = 80.0
MEMORY_HIGH_PERCENT = 85.0
MEMORY_LOW_AVAILABLE_GB = 1.0
DISK_HIGH_PERCENT = 85.0
# CPU running well below its rated max while busy can indicate throttling.
CPU_THROTTLE_FREQ_RATIO = 0.6
CPU_THROTTLE_MIN_USAGE = 50.0


@dataclass(frozen=True)
class Assessment:
    additional_tools: tuple[str, ...]
    reasons: tuple[str, ...]


class EvidenceAssessor:
    def assess(
        self,
        problem_description: str,  # kept for API compatibility; not used for rules
        evidence: Iterable[ToolResult],
        executed_tools: Iterable[str] = (),
    ) -> Assessment:
        executed = set(executed_tools)
        candidates: list[str] = []
        reasons: list[str] = []

        def recommend(tool: str, reason: str) -> None:
            if tool not in executed and tool not in candidates:
                candidates.append(tool)
                reasons.append(f"{tool}: {reason}")

        for item in evidence:
            if getattr(item.status, "value", item.status) != "success":
                continue  # failed measurement == unknown, not a signal
            payload = item.payload
            if not isinstance(payload, dict):
                continue

            name = item.tool_name.casefold()
            if name == "cpu":
                self._assess_cpu(payload, recommend)
            elif name == "memory":
                self._assess_memory(payload, recommend)
            elif name == "disk":
                self._assess_disk(payload, recommend)

        return Assessment(tuple(candidates), tuple(reasons))

    # -- per-tool rules ---------------------------------------------------

    def _assess_cpu(self, payload: dict[str, Any], recommend) -> None:
        usage = self._percent(payload.get("usage_percent"))
        if usage is None:
            return
        if usage >= CPU_HIGH_PERCENT:
            recommend("memory", f"CPU utilization is elevated ({usage:g}%)")
            recommend("startup", f"CPU utilization is elevated ({usage:g}%); check background apps")

        current = self._positive(payload.get("current_frequency"))
        maximum = self._positive(payload.get("max_frequency"))
        if (
            current is not None
            and maximum is not None
            and usage >= CPU_THROTTLE_MIN_USAGE
            and current / maximum < CPU_THROTTLE_FREQ_RATIO
        ):
            recommend(
                "temperature",
                f"CPU is busy ({usage:g}%) but running at {current:g} of {maximum:g} GHz; "
                "possible thermal throttling",
            )

    def _assess_memory(self, payload: dict[str, Any], recommend) -> None:
        used = self._percent(payload.get("usage_percent"))
        if used is not None and used >= MEMORY_HIGH_PERCENT:
            recommend("cpu", f"memory use is high ({used:g}%)")
            recommend("startup", f"memory use is high ({used:g}%); check background apps")

        available = self._non_negative(payload.get("available_gb"))
        if available is not None and available < MEMORY_LOW_AVAILABLE_GB:
            recommend("cpu", f"only {available:g} GB of memory is available")

    def _assess_disk(self, payload: dict[str, Any], recommend) -> None:
        volumes = payload.get("volumes")
        if not isinstance(volumes, list):
            return
        for volume in volumes:
            if not isinstance(volume, dict):
                continue
            used = self._percent(volume.get("usage_percent"))
            if used is not None and used >= DISK_HIGH_PERCENT:
                mount = volume.get("mountpoint", "a volume")
                recommend("startup", f"{mount} is {used:g}% full")
                recommend("memory", f"{mount} is {used:g}% full; paging needs free disk space")

    # -- value validation -------------------------------------------------

    @staticmethod
    def _number(value: Any) -> float | None:
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            return None
        number = float(value)
        return number if math.isfinite(number) else None

    @classmethod
    def _percent(cls, value: Any) -> float | None:
        number = cls._number(value)
        return number if number is not None and 0.0 <= number <= 100.0 else None

    @classmethod
    def _non_negative(cls, value: Any) -> float | None:
        number = cls._number(value)
        return number if number is not None and number >= 0.0 else None

    @classmethod
    def _positive(cls, value: Any) -> float | None:
        number = cls._number(value)
        return number if number is not None and number > 0.0 else None
