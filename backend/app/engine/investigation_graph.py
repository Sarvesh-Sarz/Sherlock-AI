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
from app.models.tool_result import ToolResult
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
        }
        return self._compiled.invoke(initial_state)

    def _plan(self, state: InvestigationGraphState) -> dict:
        plan = self._planner.create_plan(state["problem_description"])
        return {"plan": plan}

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

        return {
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
        return {"plan": replace(plan, tools_to_execute=merged_tools)}


    def _next_step(self, state: InvestigationGraphState) -> str:
        plan = state["plan"]
        if plan is None or state["iteration"] >= state["max_iterations"]:
            return "research"

        executed = set(state["executed_tools"])
        has_pending = any(tool not in executed for tool in plan.tools_to_execute)
        return "collect" if has_pending else "research"

    def _research(self, state: InvestigationGraphState) -> dict:
        results: list[ResearchResult] = []
        for query in build_research_queries(state["problem_description"], state["evidence"]):
            try:
                results.extend(self._researcher.search(query))
            except Exception as exc:  # defense in depth; research is optional
                logger.warning("Research query %r failed: %s", query, exc, exc_info=True)
        return {"research": results}

    def _reason(self, state: InvestigationGraphState) -> dict:
        plan = state["plan"]
        if plan is None:
            return {"error": "No investigation plan was produced"}

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
            return {"error": str(exc), "report": None}
        return {"report": report, "error": None}
