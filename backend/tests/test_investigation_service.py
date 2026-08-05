"""Tests for InvestigationService's own orchestration logic.

InvestigationService no longer owns a tool registry or execution logic
itself — that's entirely ToolManager's job (see tests/test_tool_manager.py
for its defense-in-depth coverage, including a tool that raises). These
tests only check that the service asks the Planner for a plan, hands
that exact plan to whatever ToolManager it's given, and attaches
whatever comes back as evidence — using fakes for both collaborators so
nothing here depends on `cpu.py` or real system state.
"""

from datetime import datetime, timezone

from app.models.investigation import CaseStatus
from app.models.investigation_plan import InvestigationPlan
from app.models.tool_result import ToolResult, ToolStatus
from app.repositories.investigation_repository import InMemoryInvestigationRepository
from app.schemas.investigation import InvestigationRequest
from app.services.investigation_service import InvestigationService


class _StubPlanner:
    """Always plans for the given tools, ignoring the description."""

    def __init__(self, tools_to_execute: list[str]) -> None:
        self._tools_to_execute = tools_to_execute

    def create_plan(self, problem_description: str) -> InvestigationPlan:
        return InvestigationPlan(
            problem_description=problem_description,
            tools_to_execute=self._tools_to_execute,
            matched_keywords=[],
            created_at=datetime.now(timezone.utc),
        )


class _StubToolManager:
    """Returns a fixed list of results and records the plan it was given."""

    def __init__(self, results: list[ToolResult]) -> None:
        self._results = results
        self.received_plan: InvestigationPlan | None = None

    def execute(self, plan: InvestigationPlan) -> list[ToolResult]:
        self.received_plan = plan
        return self._results


def test_start_investigation_attaches_whatever_the_tool_manager_returns() -> None:
    fixed_result = ToolResult(
        tool_name="cpu",
        status=ToolStatus.SUCCESS,
        collected_at=datetime.now(timezone.utc),
        payload={"usage_percent": 12.3},
    )
    tool_manager = _StubToolManager(results=[fixed_result])

    service = InvestigationService(
        repository=InMemoryInvestigationRepository(),
        planner=_StubPlanner(tools_to_execute=["cpu"]),
        tool_manager=tool_manager,
    )
    investigation = service.start_investigation(
        InvestigationRequest(problem_description="Anything.")
    )

    assert investigation.status == CaseStatus.INVESTIGATING
    assert investigation.evidence == [fixed_result]

    # The plan the service built was actually handed to the tool
    # manager — proving the two are wired together, not just each
    # independently functional in isolation.
    assert tool_manager.received_plan is not None
    assert tool_manager.received_plan.tools_to_execute == ["cpu"]


def test_start_investigation_handles_a_tool_manager_that_returns_nothing() -> None:
    """A plan whose tools aren't implemented yet should still produce a
    usable, empty-evidence case — not an error. ToolManager is the thing
    that actually decides what's implemented; the service just accepts
    whatever list it gets back, including an empty one.
    """
    service = InvestigationService(
        repository=InMemoryInvestigationRepository(),
        planner=_StubPlanner(tools_to_execute=["memory", "disk"]),
        tool_manager=_StubToolManager(results=[]),
    )
    investigation = service.start_investigation(
        InvestigationRequest(problem_description="Irrelevant for this test.")
    )

    assert investigation.evidence == []
    assert investigation.status == CaseStatus.INVESTIGATING
