"""Future reasoning pipeline for an investigation.

Planning and tool execution are implemented — see
`app.planner.planner.Planner` and `app.tools.tool_manager.ToolManager` —
and are no longer placeholders here. The stages below are still not
implemented; each module's docstring explains what it will eventually
do:

    Planner -> ToolManager -> Reasoner -> ReportGenerator
    (done)      (done)            ^              |
                                   +---- Memory --+

Reasoner: interprets results and decides what happens next.
Memory: retains context within and across investigations.
ReportGenerator: turns a resolved case into a human-readable report.
"""

from app.engine.memory import Memory
from app.engine.reasoner import Reasoner
from app.engine.report_generator import ReportGenerator

__all__ = [
    "Reasoner",
    "Memory",
    "ReportGenerator",
]
