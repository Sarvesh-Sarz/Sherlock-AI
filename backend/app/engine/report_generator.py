"""Report Generator — produces the final human-readable report for a case.

Not implemented yet. Takes a resolved investigation (plan, tool results,
reasoning trail) and turns it into the summary the user actually reads —
what was wrong, why, and what to do about it.
"""

from app.models.investigation import Investigation


class ReportGenerator:
    """Placeholder for the reporting stage of an investigation."""

    def generate(self, investigation: Investigation) -> str:
        """Produce a final report for a resolved investigation.

        Raises:
            NotImplementedError: Always, until reporting is implemented.
        """
        raise NotImplementedError("ReportGenerator is not implemented yet.")
