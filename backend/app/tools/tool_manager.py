"""Tool Manager.

Owns the registry of diagnostic tools Sherlock actually knows how to
run, and executes whichever of a plan's tools are implemented. This is
the one seam `InvestigationService` talks to instead of knowing about
individual tools (`cpu.py`, `memory.py`, and later `disk.py`, ...)
directly — adding a new tool means registering it here, not touching
the service.
"""

import logging
from collections.abc import Callable
from datetime import datetime, timezone

from app.models.investigation_plan import InvestigationPlan
from app.models.tool_result import ToolResult, ToolStatus
from app.tools import cpu, memory

logger = logging.getLogger(__name__)


class ToolManager:
    """Executes the diagnostic tools a plan calls for."""

    # Tools Sherlock actually knows how to run today. Each future tool
    # (disk, battery, wifi, startup) is added by appending a (name, run)
    # pair here — nothing else in this class, or in InvestigationService,
    # needs to change for that.
    #
    # This is a *capability* registry, separate from what a Planner
    # calls for: a plan can name tools that aren't implemented yet (see
    # `execute`), and those are skipped rather than erroring.
    #
    # A class attribute rather than module-level data (like the old
    # `_DIAGNOSTIC_TOOLS` it replaces) so the registry is unambiguously
    # ToolManager's own, per requirement #3 — not something a caller
    # could import and mutate independently of the class that owns it.
    _REGISTRY: list[tuple[str, Callable[[], ToolResult]]] = [
        ("cpu", cpu.run),
        ("memory", memory.run),
    ]

    def execute(self, plan: InvestigationPlan) -> list[ToolResult]:
        """Run every tool `plan.tools_to_execute` calls for that's implemented.

        Tools the plan names but Sherlock doesn't have yet (e.g.
        "disk", "battery", "wifi", "startup") are skipped silently —
        that's expected today, not an error, since only `cpu` and
        `memory` are implemented so far.

        Every registered tool already guards its own failures and
        returns an error `ToolResult` instead of raising (see
        `app.tools.cpu.run`). The try/except here is defense in depth
        for a future tool that doesn't hold to that contract — one
        broken tool must never take down the rest of the investigation.
        """
        planned_tools = set(plan.tools_to_execute)
        results: list[ToolResult] = []

        for tool_name, run_tool in self._REGISTRY:
            if tool_name not in planned_tools:
                continue

            try:
                result = run_tool()
            except Exception as exc:  # noqa: BLE001 — see docstring above.
                logger.error(
                    "Diagnostic tool '%s' raised unexpectedly: %s",
                    tool_name,
                    exc,
                    exc_info=True,
                )
                result = ToolResult(
                    tool_name=tool_name,
                    status=ToolStatus.ERROR,
                    collected_at=datetime.now(timezone.utc),
                    payload={"error": str(exc)},
                )
            results.append(result)

        return results
