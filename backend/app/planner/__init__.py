"""Rule-based investigation planning.

`Planner.create_plan()` (see `planner.py`) turns a plain-language
problem description into an `InvestigationPlan` — an ordered list of
diagnostic tools worth running — using the keyword rules in `rules.py`.
`InvestigationService` calls this before running any tools.
"""

from app.planner.planner import Planner

__all__ = ["Planner"]
