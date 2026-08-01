"""Memory — retains context within and across investigations.

Not implemented yet. Within a single case, this will hold plan state and
tool results as an investigation progresses. Across cases, it's the
future home of anything worth remembering about a given machine between
runs (e.g. "we already ruled out X last time"). Deliberately separate
from `InvestigationRepository`, which stores case records for the API,
not reasoning context.
"""

from typing import Any


class Memory:
    """Placeholder for the context-retention stage of an investigation."""

    def remember(self, key: str, value: Any) -> None:
        """Store a piece of context.

        Raises:
            NotImplementedError: Always, until memory is implemented.
        """
        raise NotImplementedError("Memory is not implemented yet.")

    def recall(self, key: str) -> Any:
        """Retrieve a previously stored piece of context.

        Raises:
            NotImplementedError: Always, until memory is implemented.
        """
        raise NotImplementedError("Memory is not implemented yet.")
