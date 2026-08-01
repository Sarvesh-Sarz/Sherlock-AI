"""Investigation service.

The single place that coordinates an investigation's lifecycle. Today it
creates a case, runs the available diagnostic tools against it, and
persists the result via a repository. Once the reasoning pipeline
exists, this is also where Planner, Tool Manager, Reasoner, Memory and
Report Generator get orchestrated — the constructor already accepts
them as optional collaborators so that wiring point doesn't move later.
"""

import logging
from collections.abc import Callable
from datetime import datetime, timezone

from app.engine.memory import Memory
from app.engine.planner import Planner
from app.engine.reasoner import Reasoner
from app.engine.report_generator import ReportGenerator
from app.engine.tool_manager import ToolManager
from app.models.investigation import CaseStatus, Investigation
from app.models.tool_result import ToolResult, ToolStatus
from app.repositories.investigation_repository import InvestigationRepository
from app.schemas.investigation import InvestigationRequest
from app.tools import cpu

logger = logging.getLogger(__name__)

# Diagnostic tools run for every investigation today. Each future tool
# (memory, disk, battery, wifi, startup) is added to Sherlock by
# appending a (name, run) pair here — nothing else in this file needs to
# change for that. Once a real Tool Manager exists (see
# `app.agents.tool_manager`), this list and the loop that consumes it
# move there; InvestigationService will call it instead of looping
# directly.
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

        # Reserved for future use — none of these are called yet.
        # Accepting them here now means adding real implementations later
        # is a matter of passing them in, not changing this signature.
        self._planner = planner
        self._tool_manager = tool_manager
        self._reasoner = reasoner
        self._memory = memory
        self._report_generator = report_generator

    def start_investigation(self, request: InvestigationRequest) -> Investigation:
        """Open a new investigation, run diagnostics, and persist the result.

        Evidence is collected before the case is first persisted, so the
        repository only ever holds a complete record for this path — no
        request can observe a case that's "received" but not yet
        investigated. Every tool call is synchronous and inline with the
        request, which is why each tool guards its own execution time
        and never raises (see `app.tools.cpu.run`).

        Future: hand the plain-language description to `self._planner`
        first, so it decides *which* tools to run, instead of always
        running the full list unconditionally.
        """
        investigation = Investigation.new(request.problem_description)
        self._collect_evidence(investigation)
        self._repository.add(investigation)
        return investigation

    def get_investigation(self, case_id: str) -> Investigation | None:
        """Look up an investigation by ID. Returns None if it doesn't exist."""
        return self._repository.get(case_id)

    def _collect_evidence(self, investigation: Investigation) -> None:
        """Run each registered diagnostic tool and attach its result.

        Every tool in `_DIAGNOSTIC_TOOLS` already guards its own failures
        and returns an error `ToolResult` instead of raising. The
        try/except here is defense in depth for a future tool that
        doesn't hold to that contract — one broken tool must never take
        down investigation intake for everyone.
        """
        for tool_name, run_tool in _DIAGNOSTIC_TOOLS:
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
