"""Planner — turns a problem description into an investigation plan.

Not implemented yet. This is where a problem description gets broken
down into an ordered set of steps (which tools to run, in what order,
under what conditions) — most likely produced by an LLM call once the
AI layer exists.
"""

from typing import Any


class Planner:
    """Placeholder for the planning stage of an investigation."""

    def create_plan(self, problem_description: str) -> Any:
        """Produce an investigation plan from a problem description.

        Raises:
            NotImplementedError: Always, until planning is implemented.
        """
        raise NotImplementedError("Planner is not implemented yet.")
