"""Investigation service.

The single place that coordinates an investigation's lifecycle. Today
it creates a case, asks the Planner which tools are worth running,
hands that plan to the Tool Manager, researches focused questions
derived from the complaint and evidence, and asks the Reasoner to turn
evidence + research into a report — then persists the result via a
repository.

It knows nothing about individual tools, search providers, or reasoning
implementations — those are entirely ToolManager's, Researcher's, and
Reasoner's responsibilities respectively. It only orchestrates the
sequence and handles the failure modes each stage can produce (a tool
failing, research being unavailable, reasoning failing) without
discarding whatever was already collected. Memory and Report Generator
remain reserved for future use — the constructor already accepts them
as optional collaborators so that wiring point doesn't move later.
"""

import logging

from app.engine.memory import Memory
from app.engine.report_generator import ReportGenerator
from app.models.investigation import CaseStatus, Investigation
from app.models.investigation_plan import InvestigationPlan
from app.models.research_result import ResearchResult
from app.planner.planner import Planner
from app.reasoning.baseline_reasoner import BaselineReasoner
from app.reasoning.query_builder import build_research_queries
from app.reasoning.reasoner import Reasoner
from app.repositories.investigation_repository import InvestigationRepository
from app.research.researcher import Researcher, UnconfiguredResearcher
from app.schemas.investigation import InvestigationRequest
from app.tools.tool_manager import ToolManager

logger = logging.getLogger(__name__)


class InvestigationService:
    """Coordinates the lifecycle of an investigation, start to finish."""

    def __init__(
        self,
        repository: InvestigationRepository,
        planner: Planner | None = None,
        tool_manager: ToolManager | None = None,
        researcher: Researcher | None = None,
        reasoner: Reasoner | None = None,
        memory: Memory | None = None,
        report_generator: ReportGenerator | None = None,
    ) -> None:
        self._repository = repository

        # Planner, Tool Manager, Researcher, and Reasoner are all real
        # and used below. Each defaults to a safe, zero-configuration
        # implementation rather than being required, so callers that
        # don't need to override them (most tests, quick scripts) don't
        # have to construct one — while staying overridable, e.g. to
        # inject a stub in a test, or a configured TavilyResearcher /
        # OllamaReasoner+FallbackReasoner in production (see app.api.deps).
        self._planner = planner or Planner()
        self._tool_manager = tool_manager or ToolManager()
        self._researcher = researcher or UnconfiguredResearcher()
        self._reasoner = reasoner or BaselineReasoner()

        # Reserved for future use — neither is called yet. Accepting
        # them here means wiring in a real implementation later is a
        # matter of passing it in, not changing this signature.
        self._memory = memory
        self._report_generator = report_generator

    def start_investigation(self, request: InvestigationRequest) -> Investigation:
        """Open a new investigation and run it through the full pipeline.

        Plan -> collect evidence -> research -> reason -> persist. Each
        stage after planning is allowed to come back partial or empty
        without aborting the ones after it: evidence collection
        tolerates individual tool failures (see `ToolManager.execute`),
        research tolerates being entirely unconfigured or failing (see
        `_research_evidence`), and only a reasoning failure changes the
        case's final status — see `_reason_over_evidence`. The case is
        persisted exactly once, after all of this, so the repository
        never holds a partially-updated record for this path.
        """
        investigation = Investigation.new(request.problem_description)

        plan = self._planner.create_plan(request.problem_description)
        investigation.set_plan(plan)

        self._collect_evidence(investigation, plan)
        research = self._research_evidence(investigation)
        self._reason_over_evidence(investigation, plan, research)

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

    def _research_evidence(self, investigation: Investigation) -> list[ResearchResult]:
        """Look up focused questions derived from the complaint and the
        evidence just collected.

        Queries are built from the complaint and evidence signals, never
        from the raw evidence payload (see `app.reasoning.query_builder`).
        The Researcher itself never raises and returns `[]` when
        unconfigured (see `Researcher.search`'s contract) — the
        try/except here is defense in depth for a future implementation
        that doesn't hold to that contract, the same role it plays
        around tool execution in `ToolManager.execute`. Either way,
        research coming back empty is never treated as a failure: it's
        a normal, expected outcome the Reasoner (and the eventual
        report's `research_notice`) handle directly.
        """
        results: list[ResearchResult] = []
        for query in build_research_queries(investigation.problem_description, investigation.evidence):
            try:
                results.extend(self._researcher.search(query))
            except Exception as exc:  # noqa: BLE001 — see docstring above.
                logger.warning("Research query %r failed unexpectedly: %s", query, exc, exc_info=True)
        return results

    def _reason_over_evidence(
        self,
        investigation: Investigation,
        plan: InvestigationPlan,
        research: list[ResearchResult],
    ) -> None:
        """Ask the Reasoner for a report and attach it, or mark the case
        FAILED without fabricating one.

        Unlike tool or research failures, a Reasoner is explicitly
        allowed to raise (see `Reasoner.investigate`'s contract) — this
        is the one place that's caught, so a broken or unreachable
        reasoning backend degrades the case's status instead of
        discarding the plan and evidence already collected.
        """
        investigation.mark_status(CaseStatus.REASONING)
        try:
            report = self._reasoner.investigate(
                case_id=investigation.case_id,
                problem_description=investigation.problem_description,
                plan=plan,
                evidence=investigation.evidence,
                research=research,
            )
        except Exception as exc:  # noqa: BLE001 — see docstring above.
            logger.error(
                "Reasoning failed for case %s: %s", investigation.case_id, exc, exc_info=True
            )
            investigation.mark_status(CaseStatus.FAILED)
            return

        investigation.set_report(report)
        investigation.mark_status(CaseStatus.RESOLVED)
