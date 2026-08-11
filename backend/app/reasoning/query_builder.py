"""Builds focused research queries from evidence — never from the raw
evidence payload itself.

Reads from the same `detect_signals` evidence-interpretation logic
`app.reasoning.baseline_reasoner` uses for hypotheses, so "what's worth
searching for" and "what's worth hypothesizing about" can never drift
apart — a signal strong enough to become a hypothesis is exactly a
signal worth researching, and vice versa.
"""

from app.models.tool_result import ToolResult
from app.reasoning.signals import detect_signals

_MAX_QUERIES = 3


def build_research_queries(evidence: list[ToolResult]) -> list[str]:
    """Return a short list of focused technical queries derived from evidence.

    De-duplicated (multiple disk volumes over threshold all map to the
    same query) and capped at `_MAX_QUERIES`, since each query becomes
    a real outbound network call once a research provider is
    configured — this intentionally stays small rather than
    interrogating every possible angle.
    """
    queries: list[str] = []
    for signal in detect_signals(evidence):
        if signal.research_query not in queries:
            queries.append(signal.research_query)

    return queries[:_MAX_QUERIES]
