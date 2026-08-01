"""Investigation service.

The single place that coordinates an investigation's lifecycle. Today it
only creates and retrieves case records via a repository. Once the
reasoning pipeline exists, this is also where Planner, Tool Manager,
Reasoner, Memory and Report Generator get orchestrated — the constructor
already accepts them as optional collaborators so that wiring point
doesn't move later.
"""

from app.engine.memory import Memory
from app.engine.planner import Planner
from app.engine.reasoner import Reasoner
from app.engine.report_generator import ReportGenerator
from app.engine.tool_manager import ToolManager
from app.models.investigation import Investigation
from app.repositories.investigation_repository import InvestigationRepository
from app.schemas.investigation import InvestigationRequest


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
        """Open a new investigation and persist its initial state.

        Future: hand the plain-language description to `self._planner`
        to produce a plan, rather than just recording intake.
        """
        investigation = Investigation.new(request.problem_description)
        self._repository.add(investigation)
        return investigation

    def get_investigation(self, case_id: str) -> Investigation | None:
        """Look up an investigation by ID. Returns None if it doesn't exist."""
        return self._repository.get(case_id)
