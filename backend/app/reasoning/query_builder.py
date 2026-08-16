"""Builds focused research queries from the complaint and evidence —
never from the raw evidence payload itself.

Two sources of queries, kept deliberately distinct:

- A single query grounded in the user's own words (the complaint),
  since evidence-only queries can miss what's actually being asked
  about (e.g. "Windows startup takes 5 minutes" produces no disk/memory/
  startup-entry signal on its own, but is still worth researching).
- Evidence-derived queries, read from the same `detect_signals`
  evidence-interpretation logic `app.reasoning.baseline_reasoner` uses
  for hypotheses, so "what's worth searching for" and "what's worth
  hypothesizing about" can never drift apart — a signal strong enough
  to become a hypothesis is exactly a signal worth researching, and
  vice versa.

Neither source ever includes the raw evidence payload itself (a
mountpoint, a percentage, a registry value) — see each query's own
construction below for why that's true by construction, not just by
convention.
"""

from app.models.tool_result import ToolResult
from app.reasoning.signals import detect_signals

_MAX_QUERIES = 3


def build_research_queries(problem_description: str, evidence: list[ToolResult]) -> list[str]:
    """Return a short list of focused technical queries.

    De-duplicated (multiple disk volumes over threshold all map to the
    same query) and capped at `_MAX_QUERIES`, since each query becomes
    a real outbound network call once a research provider is
    configured — this intentionally stays small rather than
    interrogating every possible angle. The cap is unchanged from
    before the complaint was added as a query source: the general
    query now competes for one of the same three slots rather than
    getting a slot of its own, so evidence-heavy cases (e.g. all of
    disk/memory/startup signaling at once) can still lose the general
    query, or an evidence query, to the cap — same trade-off that
    already existed between evidence signals themselves.
    """
    queries: list[str] = []

    general_query = _build_general_query(problem_description)
    if general_query is not None:
        queries.append(general_query)

    for signal in detect_signals(evidence):
        if signal.research_query not in queries:
            queries.append(signal.research_query)

    return queries[:_MAX_QUERIES]


def _build_general_query(problem_description: str) -> str | None:
    """Turn the complaint itself into one focused query.

    Just the complaint's own words plus a "Windows" anchor — never
    anything from the evidence payload appended here, and never the
    complaint quoted back verbatim without context (a bare user
    sentence isn't necessarily a good search query on its own; "Windows"
    grounds it as a technical query rather than open-ended text).
    """
    trimmed = problem_description.strip().rstrip(".")
    if not trimmed:
        return None
    return f"Windows {trimmed}"
