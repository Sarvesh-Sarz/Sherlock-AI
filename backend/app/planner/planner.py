"""Rule-based investigation planner.

Turns a plain-language problem description into an ordered list of
tools worth running, using simple keyword matching against the table in
`rules.py`. No AI/NLP involved — this is a deterministic, easily
tested placeholder strategy, the same way `app.tools.cpu` is a
placeholder diagnostic suite: real and working today, swappable for
something smarter (e.g. an LLM-backed planner) later without moving
where it's called from.
"""

import re
from datetime import datetime, timezone

from app.models.investigation_plan import InvestigationPlan
from app.planner.rules import DEFAULT_TOOLS, KEYWORD_RULES


class Planner:
    """Produces an `InvestigationPlan` from a problem description."""

    def create_plan(self, problem_description: str) -> InvestigationPlan:
        """Match keywords in the description and collect the tools they imply.

        Every rule is checked (not just the first match) so a
        description like "my battery is hot" plans for both the
        "battery" and "hot" rules at once. Tools are de-duplicated,
        keeping first-seen order, so a tool implied by two matched
        rules (e.g. "cpu" from both "slow" and "hot") only appears once.
        """
        normalized_description = problem_description.lower()

        tools_to_execute: list[str] = []
        matched_keywords: list[str] = []

        for keyword, implied_tools in KEYWORD_RULES.items():
            if not _contains_keyword(normalized_description, keyword):
                continue

            matched_keywords.append(keyword)
            for tool in implied_tools:
                if tool not in tools_to_execute:
                    tools_to_execute.append(tool)

        if not tools_to_execute:
            tools_to_execute = list(DEFAULT_TOOLS)

        return InvestigationPlan(
            problem_description=problem_description,
            tools_to_execute=tools_to_execute,
            matched_keywords=matched_keywords,
            created_at=datetime.now(timezone.utc),
        )


def _contains_keyword(normalized_text: str, keyword: str) -> bool:
    """Whole-word, case-insensitive match.

    A plain substring check (`keyword in text`) would false-positive on
    e.g. "hot" inside "hotel" or "shot" — word boundaries avoid that.
    `normalized_text` is expected to already be lowercased by the
    caller; `keyword` is lowered here too so `rules.py` isn't required
    to keep its keys lowercase to stay correct.
    """
    pattern = rf"\b{re.escape(keyword.lower())}\b"
    return re.search(pattern, normalized_text) is not None
