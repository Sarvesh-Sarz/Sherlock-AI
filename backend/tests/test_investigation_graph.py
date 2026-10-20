from datetime import datetime, timezone

import pytest

from app.engine.investigation_graph import InvestigationGraph
from app.models.investigation_plan import InvestigationPlan
from app.models.tool_result import ToolResult, ToolStatus


class FakePlanner:
    def create_plan(self, problem_description):
        tools = ["cpu"]
        keywords = []
        if "reveal-memory" in problem_description:
            tools.append("memory")
            keywords.append("reveal-memory")
        return InvestigationPlan(
            problem_description=problem_description,
            tools_to_execute=tools,
            matched_keywords=keywords,
            created_at=datetime.now(timezone.utc),
        )


class FakeToolManager:
    def __init__(self):
        self.calls = []

    def execute(self, plan):
        self.calls.append(list(plan.tools_to_execute))
        return [
            ToolResult(
                tool_name=name,
                status=ToolStatus.SUCCESS,
                collected_at=datetime.now(timezone.utc),
                payload={"finding": "reveal-memory"} if name == "cpu" else {"usage": 42},
            )
            for name in plan.tools_to_execute
        ]


class FakeResearcher:
    def search(self, query):
        return []


class FakeReasoner:
    def __init__(self, should_fail=False):
        self.should_fail = should_fail
        self.calls = []

    def investigate(self, **kwargs):
        self.calls.append(kwargs)
        if self.should_fail:
            raise RuntimeError("reasoner offline")
        return {"summary": "test report"}


def make_graph(*, max_iterations=3, should_fail=False):
    manager = FakeToolManager()
    reasoner = FakeReasoner(should_fail=should_fail)
    graph = InvestigationGraph(
        planner=FakePlanner(),
        tool_manager=manager,
        researcher=FakeResearcher(),
        reasoner=reasoner,
        max_iterations=max_iterations,
    )
    return graph, manager, reasoner


def test_graph_replans_from_evidence_and_runs_new_tool():
    graph, manager, reasoner = make_graph()
    result = graph.run(case_id="case-1", problem_description="general issue")

    assert manager.calls == [["cpu"], ["memory"]]
    assert result["executed_tools"] == ["cpu", "memory"]
    assert result["iteration"] == 2
    assert result["report"] == {"summary": "test report"}
    assert result["error"] is None
    assert len(reasoner.calls) == 1


def test_graph_respects_max_iterations():
    graph, manager, _ = make_graph(max_iterations=1)
    result = graph.run(case_id="case-2", problem_description="general issue")

    assert manager.calls == [["cpu"]]
    assert result["iteration"] == 1
    assert "memory" in result["plan"].tools_to_execute
    assert result["executed_tools"] == ["cpu"]


def test_reasoner_failure_is_returned_for_service_to_handle():
    graph, _, _ = make_graph(should_fail=True)
    result = graph.run(case_id="case-3", problem_description="general issue")

    assert result["report"] is None
    assert result["error"] == "reasoner offline"


def test_max_iterations_must_be_positive():
    with pytest.raises(ValueError, match="max_iterations"):
        make_graph(max_iterations=0)
