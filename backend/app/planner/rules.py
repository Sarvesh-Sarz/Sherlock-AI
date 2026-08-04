"""Keyword-to-tool rules used by the Planner.

Deliberately data, not logic — a single mapping of keyword -> tools it
implies. `planner.py` is the only thing that reads this file; keeping
rules separate from matching means adding or tuning a rule never touches
matching logic, and the table stays easy to read (and extend) on its
own once more tools exist.

Each keyword is matched as a *whole word* within the problem
description (see `planner._contains_keyword`), not a raw substring — so
"hot" doesn't also match inside "hotel", and "wifi" doesn't match inside
some unrelated longer word.

This is intentionally simple pattern matching, not NLP: it won't catch
synonyms, typos, or variant spellings ("Wi-Fi" vs "wifi"). That's an
accepted limitation of a keyword-based planner, not a bug — see the
Planner's docstring.
"""

KEYWORD_RULES: dict[str, list[str]] = {
    "slow": ["cpu", "memory", "startup", "disk"],
    "wifi": ["wifi", "internet"],
    "battery": ["battery", "cpu", "startup"],
    "hot": ["cpu", "temperature"],
}

# Used when no keyword in the description matches any rule above, so an
# investigation never opens with literally nothing planned.
DEFAULT_TOOLS: list[str] = ["cpu"]
