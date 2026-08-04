"""Dependency wiring for the API layer.

FastAPI's `Depends` calls these functions to build request handlers'
arguments. Keeping the wiring here — rather than instantiating services
inside endpoint functions — means endpoints stay easy to test and the
swap from in-memory storage to a real database touches only
`get_investigation_repository`.
"""

from functools import lru_cache

from app.planner.planner import Planner
from app.repositories.investigation_repository import (
    InMemoryInvestigationRepository,
    InvestigationRepository,
)
from app.services.investigation_service import InvestigationService


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


def get_investigation_service() -> InvestigationService:
    """Build an InvestigationService for the current request."""
    return InvestigationService(
        repository=get_investigation_repository(),
        planner=get_planner(),
    )
