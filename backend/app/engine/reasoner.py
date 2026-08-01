"""Reasoner — interprets tool output and decides what happens next.

Not implemented yet. This is where results from the Tool Manager get
evaluated against the current plan: whether a cause has been found,
whether another tool run is warranted, or whether the plan itself needs
to change.
"""

from typing import Any


class Reasoner:
    """Placeholder for the reasoning stage of an investigation."""

    def evaluate(self, *args: Any, **kwargs: Any) -> Any:
        """Interpret current findings and decide the next action.

        Raises:
            NotImplementedError: Always, until reasoning is implemented.
        """
        raise NotImplementedError("Reasoner is not implemented yet.")
