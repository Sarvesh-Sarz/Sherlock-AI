"""Investigation service.

The single place that coordinates an investigation's lifecycle. Today it
creates a case, asks the Planner which tools are worth running, runs
whichever of those are actually implemented, and persists the result via
a repository. Once the rest of the reasoning pipeline exists, this is
also where Tool Manager, Reasoner, Memory and Report Generator get
orchestrated — the constructor already accepts them as optional
collaborators so that wiring point doesn't move later.
"""

import logging
from collections.abc import Callable
from datetime import datetime, timezone

from app.engine.memory import Memory
from app.engine.reasoner import Reasoner
from app.engine.report_generator import ReportGenerator
from app.engine.tool_manager import ToolManager
from app.models.investigation import CaseStatus, Investigation
from app.models.investigation_plan import InvestigationPlan
from app.models.tool_result import ToolResult, ToolStatus
from app.planner.planner import Planner
from app.repositories.investigation_repository import InvestigationRepository
from app.schemas.investigation import InvestigationRequest
from app.tools import cpu

logger = logging.getLogger(__name__)

# Diagnostic tools Sherlock actually knows how to run today. Each future
# tool (memory, disk, battery, wifi, startup) is added by appending a
# (name, run) pair here — nothing else in this file needs to change for
# that. Once a real Tool Manager exists (see `app.agents.tool_manager`),
# this list and the loop that consumes it move there.
#
# Note this is a *capability* registry, separate from the Planner's
# rules: the Planner can call for tools (e.g. "memory", "disk") that
# aren't implemented yet — see `_collect_evidence`, which only runs the
# intersection of "planned" and "implemented".
#
# The name is listed explicitly here rather than derived from the
# function (e.g. via __module__) so a tool that raises unexpectedly
# still gets attributed correctly in its error ToolResult, regardless of
# how its module happens to be named.
_DIAGNOSTIC_TOOLS: list[tuple[str, Callable[[], ToolResult]]] = [
    ("cpu", cpu.run),
]


class InvestigationService:
    """Coordinates the lifecycle of an investigation, start to finish."""

    def __init__(
        self,
        repository: InvestigationRepository,
        planner: Planner | None = None,
        tool_manager: ToolManager | None = None,
        reasoner: Reasoner | None = None,
        memory: Memory | None = None,
        report_generator: ReportGenerator | None = None,
    ) -> None:
        self._repository = repository

        # Planner is real and used below. It defaults to a fresh
        # instance rather than being required, so callers that don't
        # care about planning (e.g. quick scripts, most tests) don't
        # have to construct one — while still being overridable, e.g.
        # to inject a stub planner in a test.
        self._planner = planner or Planner()

        # Reserved for future use — none of these are called yet.
        # Accepting them here now means adding real implementations later
        # is a matter of passing them in, not changing this signature.
        self._tool_manager = tool_manager
        self._reasoner = reasoner
        self._memory = memory
        self._report_generator = report_generator

    def start_investigation(self, request: InvestigationRequest) -> Investigation:
        """Open a new investigation, plan it, run diagnostics, and persist it.

        Planning and evidence collection both happen before the case is
        first persisted, so the repository only ever holds a complete
        record for this path — no request can observe a case that's
        "received" but not yet planned or investigated.

        Future: once a plan can call for tools this process can't run
        synchronously (e.g. something slow, or requiring elevated
        permissions), planning and execution will need to split across
        the `PLANNING` and `INVESTIGATING` statuses instead of
        collapsing straight to `INVESTIGATING` as they do today.
        """
        investigation = Investigation.new(request.problem_description)

        plan = self._planner.create_plan(request.problem_description)
        investigation.set_plan(plan)

        self._collect_evidence(investigation, plan)
        self._repository.add(investigation)
        return investigation

    def get_investigation(self, case_id: str) -> Investigation | None:
        """Look up an investigation by ID. Returns None if it doesn't exist."""
        return self._repository.get(case_id)

    def _collect_evidence(self, investigation: Investigation, plan: InvestigationPlan) -> None:
        """Run whichever planned tools are actually implemented.

        A plan can call for tools that don't exist yet — e.g. the
        "slow" rule plans memory/startup/disk alongside cpu — and those
        are silently skipped rather than erroring, since Sherlock only
        has one working tool today. Adding memory.py etc. later means
        they start running automatically the moment they're registered
        in `_DIAGNOSTIC_TOOLS`, with no change needed here or in the
        Planner.

        Every tool in `_DIAGNOSTIC_TOOLS` already guards its own
        failures and returns an error `ToolResult` instead of raising.
        The try/except here is defense in depth for a future tool that
        doesn't hold to that contract — one broken tool must never take
        down investigation intake for everyone.
        """
        planned_tools = set(plan.tools_to_execute)

        for tool_name, run_tool in _DIAGNOSTIC_TOOLS:
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
            investigation.add_evidence(result)

        investigation.mark_status(CaseStatus.INVESTIGATING)
