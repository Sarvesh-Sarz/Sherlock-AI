"""Dependency wiring for the API layer.

FastAPI's `Depends` calls these functions to build request handlers'
arguments. Keeping the wiring here — rather than instantiating services
inside endpoint functions — means endpoints stay easy to test and the
swap from in-memory storage to a real database touches only
`get_investigation_repository`.
"""

from functools import lru_cache

from app.core.config import get_settings
from app.planner.planner import Planner
from app.reasoning.baseline_reasoner import BaselineReasoner
from app.reasoning.fallback_reasoner import FallbackReasoner
from app.reasoning.ollama_reasoner import OllamaReasoner
from app.reasoning.reasoner import Reasoner
from app.repositories.investigation_repository import (
    InMemoryInvestigationRepository,
    InvestigationRepository,
)
from app.services.investigation_service import InvestigationService
from app.tools.tool_manager import ToolManager


@lru_cache
def get_investigation_repository() -> InvestigationRepository:
    """Return the process-wide investigation repository.

    Cached so every request shares one store for now. Replace this with
    a dependency that yields a database session per request once
    persistence is introduced — callers only depend on the
    `InvestigationRepository` interface, so nothing else needs to change.
    """
    return InMemoryInvestigationRepository()


@lru_cache
def get_planner() -> Planner:
    """Return the process-wide Planner.

    Cached since `Planner` is stateless (its rules are module-level data
    in `app.planner.rules`) — a fresh instance per request would behave
    identically, this just avoids the pointless reallocation.
    """
    return Planner()


@lru_cache
def get_tool_manager() -> ToolManager:
    """Return the process-wide ToolManager.

    Cached since `ToolManager` is stateless — its registry is fixed at
    class-definition time — so one shared instance behaves identically
    to a fresh one per request.
    """
    return ToolManager()




@lru_cache
def get_reasoner() -> Reasoner:
    """Return the process-wide Reasoner.

    Tries a local Ollama-backed reasoner first and falls back to the
    deterministic `BaselineReasoner` if Ollama isn't reachable, the
    configured model isn't pulled, or its response doesn't parse into a
    valid report (see `FallbackReasoner`, `OllamaReasoner`). Sherlock
    works with zero LLM configured — exactly as it did before this
    existed — and gets richer reasoning automatically the moment a
    local model is available; nothing needs to be enabled explicitly.
    Swapping in a different local backend (AMD-optimized inference,
    another runtime) means changing this one function, not
    `InvestigationService` or anything that calls it.
    """
    settings = get_settings()
    ollama_reasoner = OllamaReasoner(
        base_url=settings.ollama_base_url,
        model=settings.ollama_model,
        timeout_seconds=settings.ollama_timeout_seconds,
    )
    return FallbackReasoner(primary=ollama_reasoner, fallback=BaselineReasoner())


def get_investigation_service() -> InvestigationService:
    """Build an InvestigationService for the current request."""
    return InvestigationService(
        repository=get_investigation_repository(),
        planner=get_planner(),
        tool_manager=get_tool_manager(),
        reasoner=get_reasoner(),
    )
