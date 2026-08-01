"""Tool Manager — registers and executes diagnostic tools.

Not implemented yet. This is where individual Windows diagnostic checks
(e.g. reading startup programs, event logs, resource usage) will be
registered and invoked on the Planner's behalf. Kept separate from the
Planner and Reasoner so tools can be added, sandboxed, and permissioned
independently of the reasoning that decides when to call them.
"""

from typing import Any


class ToolManager:
    """Placeholder for the tool-execution stage of an investigation."""

    def run_tool(self, tool_name: str, **kwargs: Any) -> Any:
        """Execute a named diagnostic tool with the given arguments.

        Raises:
            NotImplementedError: Always, until tools are implemented.
        """
        raise NotImplementedError("ToolManager is not implemented yet.")
