"""Storage for investigations.

`InvestigationRepository` is the contract the rest of the app depends on.
`InMemoryInvestigationRepository` is a throwaway implementation that
satisfies that contract for now — swapping in a real database later
(e.g. `SqlInvestigationRepository`) means changing one dependency wiring
point in `app.api.deps`, not the service or API layer.
"""

from abc import ABC, abstractmethod

from app.models.investigation import Investigation


class InvestigationRepository(ABC):
    """Persistence contract for investigations."""

    @abstractmethod
    def add(self, investigation: Investigation) -> None:
        """Store a newly created investigation."""

    @abstractmethod
    def get(self, case_id: str) -> Investigation | None:
        """Fetch an investigation by ID, or None if it doesn't exist."""

    @abstractmethod
    def update(self, investigation: Investigation) -> None:
        """Persist changes to an existing investigation."""


class InMemoryInvestigationRepository(InvestigationRepository):
    """Process-memory-only store.

    Data does not survive a restart and is not shared across worker
    processes. That's an explicit, temporary trade-off — there is no
    database in this foundation yet — not an oversight.
    """

    def __init__(self) -> None:
        self._cases: dict[str, Investigation] = {}

    def add(self, investigation: Investigation) -> None:
        self._cases[investigation.case_id] = investigation

    def get(self, case_id: str) -> Investigation | None:
        return self._cases.get(case_id)

    def update(self, investigation: Investigation) -> None:
        self._cases[investigation.case_id] = investigation
