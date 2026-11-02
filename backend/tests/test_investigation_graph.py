from datetime import datetime, timezone

import pytest

from app.engine.investigation_graph import InvestigationGraph
from app.models.investigation_plan import InvestigationPlan
from app.models.tool_result import ToolResult, ToolStatus


class FakePlanner:
    def __init__(self, tools=None):
        self.tools = tools or ["cpu"]

    def create_plan(self, problem_description):
        return InvestigationPlan(
            problem_description=problem_description,
            tools_to_execute=list(self.tools),
            matched_keywords=[],
            created_at=datetime.now(timezone.utc),
        )


class FakeToolManager:
    def __init__(self, payloads=None, status=ToolStatus.SUCCESS):
        self.calls = []
        self.payloads = payloads or {"cpu": {"usage_percent": 93.0}}
        self.status = status

    def execute(self, plan):
        self.calls.append(list(plan.tools_to_execute))
        return [
            ToolResult(
                tool_name=name,
                status=self.status,
                collected_at=datetime.now(timezone.utc),
                payload=self.payloads.get(name, {"usage_percent": 42.0}),
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


def make_graph(*, max_iterations=3, should_fail=False, payloads=None,
               status=ToolStatus.SUCCESS, planned=None):
    manager = FakeToolManager(payloads=payloads, status=status)
    reasoner = FakeReasoner(should_fail=should_fail)
    graph = InvestigationGraph(
        planner=FakePlanner(planned),
        tool_manager=manager,
        researcher=FakeResearcher(),
        reasoner=reasoner,
        max_iterations=max_iterations,
    )
    return graph, manager, reasoner


def test_high_cpu_evidence_triggers_followup_tools():
    graph, manager, reasoner = make_graph()
    result = graph.run(case_id="case-1", problem_description="general issue")

    assert manager.calls == [["cpu"], ["memory", "startup"]]
    assert result["executed_tools"] == ["cpu", "memory", "startup"]
    assert result["iteration"] == 2
    assert result["report"] == {"summary": "test report"}
    assert result["error"] is None
    assert len(reasoner.calls) == 1


def test_healthy_evidence_stops_after_first_round():
    graph, manager, _ = make_graph(payloads={"cpu": {"usage_percent": 10.0}})
    result = graph.run(case_id="case-h", problem_description="general issue")

    assert manager.calls == [["cpu"]]
    assert result["executed_tools"] == ["cpu"]
    assert result["iteration"] == 1


def test_failed_evidence_does_not_trigger_followups():
    graph, manager, _ = make_graph(status=ToolStatus.ERROR)
    result = graph.run(case_id="case-f", problem_description="general issue")

    assert manager.calls == [["cpu"]]
    assert len(result["evidence"]) == 1  # failed evidence is preserved


def test_graph_respects_max_iterations():
    graph, manager, _ = make_graph(max_iterations=1)
    result = graph.run(case_id="case-2", problem_description="general issue")

    assert manager.calls == [["cpu"]]
    assert result["iteration"] == 1
    assert "memory" in result["plan"].tools_to_execute  # decided, but not run
    assert result["executed_tools"] == ["cpu"]


def test_multi_round_never_reruns_a_tool():
    payloads = {
        "cpu": {"usage_percent": 95.0},
        "memory": {"usage_percent": 95.0, "available_gb": 0.3},
    }
    graph, manager, _ = make_graph(payloads=payloads, max_iterations=5)
    result = graph.run(case_id="case-m", problem_description="general issue")

    ran = [tool for call in manager.calls for tool in call]
    assert len(ran) == len(set(ran))
    assert result["iteration"] <= 5


def test_followup_does_not_exceed_iteration_limit_on_busy_system():
    payloads = {
        "cpu": {"usage_percent": 99.0},
        "memory": {"usage_percent": 99.0, "available_gb": 0.1},
        "startup": {"total_entries": 20},
    }
    graph, manager, _ = make_graph(payloads=payloads, max_iterations=2)
    result = graph.run(case_id="case-b", problem_description="general issue")

    assert result["iteration"] == 2
    assert len(manager.calls) == 2


def test_reasoner_failure_is_returned_for_service_to_handle():
    graph, _, _ = make_graph(should_fail=True)
    result = graph.run(case_id="case-3", problem_description="general issue")

    assert result["report"] is None
    assert result["error"] == "reasoner offline"


def test_max_iterations_must_be_positive():
    with pytest.raises(ValueError, match="max_iterations"):
        make_graph(max_iterations=0)
