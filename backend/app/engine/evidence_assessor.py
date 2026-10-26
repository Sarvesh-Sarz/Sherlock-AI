"""Conservative deterministic follow-up decisions from structured diagnostic evidence."""
from __future__ import annotations
from dataclasses import dataclass
from typing import Any, Iterable
from app.models.tool_result import ToolResult

@dataclass(frozen=True)
class Assessment:
    additional_tools: tuple[str, ...]
    reasons: tuple[str, ...]

class EvidenceAssessor:
    def assess(self, problem_description: str, evidence: Iterable[ToolResult],
               executed_tools: Iterable[str] = ()) -> Assessment:
        complaint = problem_description.casefold()
        executed = set(executed_tools)
        candidates: list[str] = []
        reasons: list[str] = []

        def recommend(tool: str, reason: str) -> None:
            if tool not in executed and tool not in candidates:
                candidates.append(tool)
                reasons.append(f"{tool}: {reason}")

        if any(w in complaint for w in ("slow", "lag", "freeze", "sluggish", "high cpu")):
            recommend("cpu", "complaint suggests a performance issue")
            recommend("memory", "memory pressure can contribute to slowdown")
            recommend("startup", "background applications can affect performance")
        if any(w in complaint for w in ("disk", "storage", "space", "drive full")):
            recommend("disk", "complaint points to storage")
        if any(w in complaint for w in ("memory", "ram", "out of memory")):
            recommend("memory", "complaint explicitly mentions memory")

        for item in evidence:
            if getattr(item.status, "value", item.status) != "success":
                continue
            payload: Any = item.payload
            if not isinstance(payload, dict):
                continue
            name = item.tool_name.casefold()
            if name == "cpu":
                value = self._number(payload, "usage_percent", "cpu_percent", "utilization_percent")
                if value is not None and value >= 80:
                    recommend("memory", f"CPU utilization is elevated ({value:g}%)")
                    recommend("startup", "elevated CPU use warrants checking background apps")
            elif name == "memory":
                used = self._number(payload, "used_percent", "memory_used_percent", "usage_percent")
                available = self._number(payload, "available_mb", "available_memory_mb", "free_mb")
                if used is not None and used >= 85:
                    recommend("cpu", f"memory use is high ({used:g}%)")
                    recommend("startup", "high memory use warrants checking background apps")
                if available is not None and available < 1024:
                    recommend("cpu", "low available memory warrants checking competing resource use")
            elif name == "disk":
                free = self._number(payload, "free_percent", "free_space_percent", "disk_free_percent")
                if free is not None and free <= 15:
                    recommend("startup", f"disk free space is low ({free:g}%)")

        return Assessment(tuple(candidates), tuple(reasons))

    @staticmethod
    def _number(payload: dict[str, Any], *keys: str) -> float | None:
        for key in keys:
            value = payload.get(key)
            if isinstance(value, (int, float)) and not isinstance(value, bool):
                return float(value)
        return None
