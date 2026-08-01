"""Future reasoning pipeline for an investigation.

None of these components are implemented yet — see each module's
docstring. They're scaffolded here as separate, single-purpose classes
so `InvestigationService` has a stable place to wire them in once they
exist, without a later restructure:

    intake -> Planner -> ToolManager -> Reasoner -> ReportGenerator
                              ^              |
                              +---- Memory --+

Planner: decides what to check.
ToolManager: runs the actual diagnostic tools.
Reasoner: interprets results and decides what happens next.
Memory: retains context within and across investigations.
ReportGenerator: turns a resolved case into a human-readable report.
"""

from app.engine.memory import Memory
from app.engine.planner import Planner
from app.engine.reasoner import Reasoner
from app.engine.report_generator import ReportGenerator
from app.engine.tool_manager import ToolManager

__all__ = [
    "Planner",
    "ToolManager",
    "Reasoner",
    "Memory",
    "ReportGenerator",
]
