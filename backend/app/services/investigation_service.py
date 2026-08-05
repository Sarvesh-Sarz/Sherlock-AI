"""Investigation service.

The single place that coordinates an investigation's lifecycle. Today it
creates a case, asks the Planner which tools are worth running, hands
that plan to the Tool Manager, and persists the result via a repository.
It knows nothing about individual tools (`cpu.py` or otherwise) — that's
entirely `ToolManager`'s responsibility. Once the rest of the reasoning
pipeline exists, this is also where Reasoner, Memory and Report
Generator get orchestrated — the constructor already accepts them as
optional collaborators so that wiring point doesn't move later.
"""

from app.engine.memory import Memory
from app.engine.reasoner import Reasoner
from app.engine.report_generator import ReportGenerator
from app.models.investigation import CaseStatus, Investigation
from app.models.investigation_plan import InvestigationPlan
from app.planner.planner import Planner
from app.repositories.investigation_repository import InvestigationRepository
from app.schemas.investigation import InvestigationRequest
from app.tools.tool_manager import ToolManager


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

        # Planner and Tool Manager are real and used below. Both default
        # to a fresh instance rather than being required, so callers
        # that don't need to override them (most tests, quick scripts)
        # don't have to construct one — while staying overridable, e.g.
        # to inject a stub in a test.
        self._planner = planner or Planner()
        self._tool_manager = tool_manager or ToolManager()

        # Reserved for future use — neither of these is called yet.
        # Accepting them here now means adding real implementations later
        # is a matter of passing them in, not changing this signature.
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
        """Attach whatever the Tool Manager reports for this plan.

        This service doesn't know which tools are implemented, or how to
        run any of them — that's entirely `ToolManager.execute`'s job,
        including tolerating a tool that fails or one the plan calls for
        that doesn't exist yet. Adding a new tool is a change to
        `ToolManager`'s registry only; nothing here needs to change.
        """
        for result in self._tool_manager.execute(plan):
            investigation.add_evidence(result)

        investigation.mark_status(CaseStatus.INVESTIGATING)
