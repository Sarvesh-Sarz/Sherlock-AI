"""Tavily-backed Researcher.

Tavily (https://tavily.com) is a search API built specifically for
grounding an AI system's claims in real, citable web results, which is
why it's the one concrete provider implemented here. Nothing outside
this file depends on Tavily specifically — everything else goes through
the `Researcher` interface (see `researcher.py`), so this class could be
swapped for a different provider without touching the Reasoner or the
investigation service.

Requires `SHERLOCK_TAVILY_API_KEY` to be set (see `.env.example`); if
it isn't, `app.api.deps.get_researcher` uses `UnconfiguredResearcher`
instead of this class entirely.
"""

import logging
from datetime import datetime, timezone
from urllib.parse import urlparse

import httpx

from app.models.research_result import ResearchResult
from app.research.researcher import Researcher

logger = logging.getLogger(__name__)

_SEARCH_URL = "https://api.tavily.com/search"
_REQUEST_TIMEOUT_SECONDS = 10.0
_MAX_RESULTS = 5


class TavilyResearcher(Researcher):
    """Searches the web via Tavily's REST API."""

    def __init__(self, api_key: str) -> None:
        self._api_key = api_key

    def search(self, query: str) -> list[ResearchResult]:
        """Query Tavily and return structured results.

        Never raises — see `Researcher.search`'s contract. A network
        failure, a non-2xx response, or a response that doesn't look
        like Tavily's documented shape all degrade to an empty list
        rather than propagating.
        """
        try:
            response = httpx.post(
                _SEARCH_URL,
                json={"api_key": self._api_key, "query": query, "max_results": _MAX_RESULTS},
                timeout=_REQUEST_TIMEOUT_SECONDS,
            )
            response.raise_for_status()
            body = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            logger.warning("Tavily search failed for query %r: %s", query, exc, exc_info=True)
            return []

        return self._parse_results(body, query)

    def _parse_results(self, body: object, query: str) -> list[ResearchResult]:
        """Defensively parse Tavily's response.

        A provider response is external input Sherlock doesn't control
        — an unexpected shape (a field renamed, a result missing its
        own URL) is treated the same as "no results" for that entry
        rather than raising or fabricating a placeholder value. A
        result missing its own citation is worse than no result at all.
        """
        raw_results = body.get("results") if isinstance(body, dict) else None
        if not isinstance(raw_results, list):
            logger.warning("Tavily returned an unexpected response shape for query %r: %r", query, body)
            return []

        retrieved_at = datetime.now(timezone.utc)
        results: list[ResearchResult] = []
        for item in raw_results:
            if not isinstance(item, dict):
                continue
            url = item.get("url")
            title = item.get("title")
            if not isinstance(url, str) or not url or not isinstance(title, str) or not title:
                continue
            results.append(
                ResearchResult(
                    title=title,
                    url=url,
                    snippet=str(item.get("content", "")),
                    source=urlparse(url).netloc or "unknown",
                    retrieved_at=retrieved_at,
                )
            )
        return results
