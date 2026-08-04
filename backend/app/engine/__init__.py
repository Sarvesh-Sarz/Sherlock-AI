"""Future reasoning pipeline for an investigation.

Planning is implemented — see `app.planner.planner.Planner` — and is no
longer a placeholder here. The stages below are still not implemented;
each module's docstring explains what it will eventually do:

    Planner -> ToolManager -> Reasoner -> ReportGenerator
    (done)         ^              |
                    +---- Memory --+

ToolManager: runs the diagnostic tools a plan calls for. Today,
InvestigationService does this directly for the one tool that exists
(see `_DIAGNOSTIC_TOOLS` in `app.services.investigation_service`); once
there are enough tools that this needs real orchestration (concurrency,
retries, per-tool timeouts), it moves here.
Reasoner: interprets results and decides what happens next.
Memory: retains context within and across investigations.
ReportGenerator: turns a resolved case into a human-readable report.
"""

from app.engine.memory import Memory
from app.engine.reasoner import Reasoner
from app.engine.report_generator import ReportGenerator
from app.engine.tool_manager import ToolManager

__all__ = [
    "ToolManager",
    "Reasoner",
    "Memory",
    "ReportGenerator",
]
