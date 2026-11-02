"""Bounded LangGraph orchestration for Sherlock AI investigations.

This module wraps the existing Planner, ToolManager, Researcher, and Reasoner
contracts. It does not run shell commands itself and never modifies the host.
Replanning is deliberately deterministic for now: the existing keyword Planner
is run against the complaint plus a compact textual representation of evidence.
"""
from __future__ import annotations

import logging
from dataclasses import replace
from datetime import datetime, timezone
from typing import TypedDict

from langgraph.graph import END, START, StateGraph

from app.models.investigation_plan import InvestigationPlan
from app.models.investigation_report import InvestigationReport
from app.models.research_result import ResearchResult
from app.models.tool_result import ToolResult, ToolStatus
from app.models.trace import TraceEvent, TraceStage
from app.planner.planner import Planner
from app.reasoning.query_builder import build_research_queries
from app.reasoning.reasoner import Reasoner
from app.research.researcher import Researcher
from app.engine.evidence_assessor import EvidenceAssessor

logger = logging.getLogger(__name__)


class InvestigationGraphState(TypedDict):
    case_id: str
    problem_description: str
    plan: InvestigationPlan | None
    evidence: list[ToolResult]
    research: list[ResearchResult]
    report: InvestigationReport | None
    executed_tools: list[str]
    iteration: int
    max_iterations: int
    error: str | None
    trace: list[TraceEvent]


class InvestigationGraph:
    """Run a bounded plan -> collect -> assess/replan -> research -> reason graph."""

    def __init__(
        self,
        planner: Planner,
        tool_manager,
        researcher: Researcher,
        reasoner: Reasoner,
        *,
        max_iterations: int = 3,
    ) -> None:
        if max_iterations < 1:
            raise ValueError("max_iterations must be at least 1")

        self._planner = planner
        self._tool_manager = tool_manager
        self._researcher = researcher
        self._reasoner = reasoner
        self._max_iterations = max_iterations
        self._assessor = EvidenceAssessor()

        graph = StateGraph(InvestigationGraphState)
        graph.add_node("plan", self._plan)
        graph.add_node("collect", self._collect)
        graph.add_node("assess", self._assess)
        graph.add_node("research", self._research)
        graph.add_node("reason", self._reason)

        graph.add_edge(START, "plan")
        graph.add_edge("plan", "collect")
        graph.add_edge("collect", "assess")
        graph.add_conditional_edges(
            "assess",
            self._next_step,
            {"collect": "collect", "research": "research"},
        )
        graph.add_edge("research", "reason")
        graph.add_edge("reason", END)
        self._compiled = graph.compile()

    def run(self, *, case_id: str, problem_description: str) -> InvestigationGraphState:
        """Execute the graph and return its final state."""
        initial_state: InvestigationGraphState = {
            "case_id": case_id,
            "problem_description": problem_description,
            "plan": None,
            "evidence": [],
            "research": [],
            "report": None,
            "executed_tools": [],
            "iteration": 0,
            "max_iterations": self._max_iterations,
            "error": None,
            "trace": [],
        }
        return self._compiled.invoke(initial_state)

    def _plan(self, state: InvestigationGraphState) -> dict:
        plan = self._planner.create_plan(state["problem_description"])
        keywords = list(getattr(plan, "matched_keywords", []) or [])
        why = f"matched keywords: {', '.join(keywords)}" if keywords else "no specific keywords matched, using the default check"
        event = TraceEvent(
            stage=TraceStage.PLAN,
            iteration=state["iteration"],
            message=f"Planned diagnostics: {', '.join(plan.tools_to_execute)} ({why}).",
            details={"tools": list(plan.tools_to_execute), "matched_keywords": keywords},
        )
        return {"plan": plan, "trace": [*state["trace"], event]}

    def _collect(self, state: InvestigationGraphState) -> dict:
        plan = state["plan"]
        if plan is None:
            raise RuntimeError("Graph reached collection without an investigation plan")

        already_executed = set(state["executed_tools"])
        pending = [name for name in plan.tools_to_execute if name not in already_executed]
        if not pending:
            return {}

        # Execute only this round's tools while preserving the existing plan contract.
        round_plan = replace(plan, tools_to_execute=pending)
        results = self._tool_manager.execute(round_plan)

        round_number = state["iteration"] + 1
        statuses = {r.tool_name: _status_value(r.status) for r in results}
        skipped = [name for name in pending if name not in statuses]
        failed = [name for name, status in statuses.items() if status != "success"]
        message = f"Round {round_number}: ran {', '.join(statuses) or 'no tools'}."
        if failed:
            message += f" Failed (treated as unknown, not normal): {', '.join(failed)}."
        if skipped:
            message += f" Not available on this system: {', '.join(skipped)}."
        event = TraceEvent(
            stage=TraceStage.COLLECT,
            iteration=round_number,
            message=message,
            details={"requested": pending, "results": statuses, "failed": failed, "skipped": skipped},
        )

        return {
            "trace": [*state["trace"], event],
            "evidence": [*state["evidence"], *results],
            # Mark requested tools as attempted even if ToolManager skips an
            # unregistered tool; otherwise the graph could loop forever.
            "executed_tools": [*state["executed_tools"], *pending],
            "iteration": state["iteration"] + 1,
        }

    def _assess(self, state: InvestigationGraphState) -> dict:
        plan = state["plan"]
        if plan is None:
            raise RuntimeError("Graph reached assessment without an investigation plan")

        assessment = self._assessor.assess(
            problem_description=state["problem_description"],
            evidence=state["evidence"],
            executed_tools=state["executed_tools"],
        )
        merged_tools = list(plan.tools_to_execute)
        for tool_name in assessment.additional_tools:
            if tool_name not in merged_tools:
                merged_tools.append(tool_name)

        if assessment.reasons:
            logger.info(
                "Evidence assessment for case %s: %s",
                state["case_id"],
                "; ".join(assessment.reasons),
            )

        executed = set(state["executed_tools"])
        not_run = [t for t in merged_tools if t not in executed]
        limit_reached = state["iteration"] >= state["max_iterations"]
        if assessment.additional_tools:
            message = "Evidence called for follow-up: " + "; ".join(assessment.reasons) + "."
            if limit_reached:
                message += (
                    f" Iteration limit ({state['max_iterations']}) reached, so these were "
                    f"not run: {', '.join(not_run)}."
                )
        elif not_run and limit_reached:
            message = (
                f"Iteration limit ({state['max_iterations']}) reached; "
                f"planned tools not run: {', '.join(not_run)}."
            )
        else:
            message = "Evidence reviewed; no further diagnostics needed."
        event = TraceEvent(
            stage=TraceStage.ASSESS,
            iteration=state["iteration"],
            message=message,
            details={
                "follow_up_tools": list(assessment.additional_tools),
                "reasons": list(assessment.reasons),
                "iteration_limit_reached": limit_reached,
                "not_run": not_run if limit_reached else [],
            },
        )
        return {
            "plan": replace(plan, tools_to_execute=merged_tools),
            "trace": [*state["trace"], event],
        }


    def _next_step(self, state: InvestigationGraphState) -> str:
        plan = state["plan"]
        if plan is None or state["iteration"] >= state["max_iterations"]:
            return "research"

        executed = set(state["executed_tools"])
        has_pending = any(tool not in executed for tool in plan.tools_to_execute)
        return "collect" if has_pending else "research"

    def _research(self, state: InvestigationGraphState) -> dict:
        results: list[ResearchResult] = []
        queries = build_research_queries(state["problem_description"], state["evidence"])
        failed_queries = 0
        for query in queries:
            try:
                results.extend(self._researcher.search(query))
            except Exception as exc:  # defense in depth; research is optional
                failed_queries += 1
                logger.warning("Research query %r failed: %s", query, exc, exc_info=True)
        message = f"Research: {len(queries)} focused queries, {len(results)} results."
        if failed_queries:
            message += f" {failed_queries} queries failed."
        if not results:
            message += " External research did not contribute to this case."
        event = TraceEvent(
            stage=TraceStage.RESEARCH,
            iteration=state["iteration"],
            message=message,
            details={"queries": len(queries), "results": len(results), "failed_queries": failed_queries},
        )
        return {"research": results, "trace": [*state["trace"], event]}

    def _reason(self, state: InvestigationGraphState) -> dict:
        plan = state["plan"]
        if plan is None:
            event = TraceEvent(
                stage=TraceStage.REASON,
                iteration=state["iteration"],
                message="Reasoning could not start: no investigation plan was produced.",
            )
            return {"error": "No investigation plan was produced", "trace": [*state["trace"], event]}

        try:
            report = self._reasoner.investigate(
                case_id=state["case_id"],
                problem_description=state["problem_description"],
                plan=plan,
                evidence=state["evidence"],
                research=state["research"],
            )
        except Exception as exc:  # the service converts this into CaseStatus.FAILED
            logger.error("Reasoning failed for case %s: %s", state["case_id"], exc, exc_info=True)
            event = TraceEvent(
                stage=TraceStage.REASON,
                iteration=state["iteration"],
                message=f"Reasoning failed: {exc}. Collected evidence was preserved; no report was invented.",
                details={"succeeded": False},
            )
            return {"error": str(exc), "report": None, "trace": [*state["trace"], event]}
        method = getattr(report, "reasoning_method", None)
        event = TraceEvent(
            stage=TraceStage.REASON,
            iteration=state["iteration"],
            message="Reasoning complete" + (f" using {method}." if method else "."),
            details={"succeeded": True, "reasoning_method": method},
        )
        return {"report": report, "error": None, "trace": [*state["trace"], event]}


def _status_value(status) -> str:
    return status.value if isinstance(status, ToolStatus) else str(status)
