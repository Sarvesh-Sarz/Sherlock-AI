"""Tests for ToolManager: the registry of implemented tools, and the
logic that runs whichever of a plan's tools are actually available.
"""

from datetime import datetime, timezone

from app.models.investigation_plan import InvestigationPlan
from app.models.tool_result import ToolStatus
from app.tools import cpu
from app.tools.tool_manager import ToolManager


def _plan(tools_to_execute: list[str]) -> InvestigationPlan:
    return InvestigationPlan(
        problem_description="Irrelevant for these tests.",
        tools_to_execute=tools_to_execute,
        matched_keywords=[],
        created_at=datetime.now(timezone.utc),
    )


def test_execute_runs_cpu_when_planned() -> None:
    results = ToolManager().execute(_plan(["cpu"]))

    assert len(results) == 1
    assert results[0].tool_name == "cpu"
    # A real psutil call — the outcome depends on the environment, but
    # it must be one of the two valid statuses, and must not raise.
    assert results[0].status in (ToolStatus.SUCCESS, ToolStatus.ERROR)


def test_execute_runs_memory_when_planned() -> None:
    results = ToolManager().execute(_plan(["memory"]))

    assert len(results) == 1
    assert results[0].tool_name == "memory"
    assert results[0].status in (ToolStatus.SUCCESS, ToolStatus.ERROR)


def test_execute_runs_both_cpu_and_memory_when_a_plan_calls_for_both() -> None:
    """The "slow" rule plans cpu, memory, startup, disk — this is what
    ToolManager actually does with that plan: run the two that exist,
    in registry order, and skip the two that don't.
    """
    results = ToolManager().execute(_plan(["cpu", "memory", "startup", "disk"]))

    assert [r.tool_name for r in results] == ["cpu", "memory"]


def test_execute_skips_planned_tools_that_are_not_implemented() -> None:
    """"disk", "battery", "wifi", and "startup" don't exist yet — a plan
    naming them must be handled gracefully, not raise or return a
    placeholder result for them.
    """
    results = ToolManager().execute(_plan(["disk", "battery", "wifi", "startup"]))

    assert results == []


def test_execute_only_runs_planned_tools_not_the_whole_registry() -> None:
    """cpu is implemented, but if the plan doesn't call for it, it must
    not run — the registry is a capability list, not an execute-all list.
    """
    results = ToolManager().execute(_plan([]))

    assert results == []


def test_execute_survives_a_tool_that_raises(monkeypatch) -> None:
    """`app.tools.cpu.run` already guards its own failures — this test
    covers ToolManager's defense in depth for a hypothetical tool that
    doesn't hold to that contract, proving one broken tool can't take
    the rest of the investigation down with it.
    """

    def _broken_tool() -> None:
        raise RuntimeError("this tool forgot to catch its own errors")

    monkeypatch.setattr(ToolManager, "_REGISTRY", [("broken", _broken_tool)])

    results = ToolManager().execute(_plan(["broken"]))

    assert len(results) == 1
    assert results[0].tool_name == "broken"
    assert results[0].status == ToolStatus.ERROR
    assert "forgot to catch" in results[0].payload["error"]


def test_execute_runs_remaining_tools_after_one_raises(monkeypatch) -> None:
    """One broken tool must not stop the rest of the registry from running."""

    def _broken_tool() -> None:
        raise RuntimeError("boom")

    monkeypatch.setattr(
        ToolManager,
        "_REGISTRY",
        [("broken", _broken_tool), ("cpu", cpu.run)],
    )

    results = ToolManager().execute(_plan(["broken", "cpu"]))

    names_to_status = {r.tool_name: r.status for r in results}
    assert names_to_status["broken"] == ToolStatus.ERROR
    assert names_to_status["cpu"] in (ToolStatus.SUCCESS, ToolStatus.ERROR)
