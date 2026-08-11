"""Research layer — read-only lookups to support the Reasoner's
hypotheses with external, citable sources.

`Researcher` is the interface. The Reasoner only ever depends on this
interface, never on how search actually happens (see
`app.reasoning.reasoner`) — search logic doesn't live inside reasoning
logic, and the concrete provider (see `tavily_researcher.py`) can be
swapped, or entirely absent (see `UnconfiguredResearcher` below),
without touching any reasoning code.

Strictly read-only: nothing in this package ever executes anything on
the user's machine or modifies system state. It only makes outbound
HTTP requests to a search provider and returns what comes back.
"""

from abc import ABC, abstractmethod

from app.models.research_result import ResearchResult


class Researcher(ABC):
    """Contract for looking up external research relevant to a query."""

    @abstractmethod
    def search(self, query: str) -> list[ResearchResult]:
        """Return structured results for a focused technical query.

        Implementations must never raise: a network failure, a
        malformed provider response, and "no provider configured" are
        all real, expected outcomes here, not exceptional ones — each
        degrades to an empty list rather than propagating, so nothing
        that calls a Researcher (the investigation service, eventually
        a Reasoner) needs special-case error handling just to ask a
        question. See `TavilyResearcher.search` for where that
        degradation actually happens.
        """


class UnconfiguredResearcher(Researcher):
    """Used when no research provider is configured.

    Not a mock or a test double — this is the real, production
    implementation for "there is no API key set". It's what
    `app.api.deps.get_researcher` wires up by default, so Sherlock
    works out of the box with zero external research configured,
    exactly as it did before this layer existed, rather than requiring
    a provider just to function.
    """

    def search(self, query: str) -> list[ResearchResult]:
        return []
