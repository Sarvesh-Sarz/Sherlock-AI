"""Research layer.

`Researcher` (see `researcher.py`) is the interface everything else in
the project depends on. `UnconfiguredResearcher` (also in
`researcher.py`) is the safe, zero-configuration default.
`TavilyResearcher` (see `tavily_researcher.py`) is the one real
provider implemented so far — swappable for another without touching
anything that calls `Researcher.search`.
"""

from app.research.researcher import Researcher, UnconfiguredResearcher
from app.research.tavily_researcher import TavilyResearcher

__all__ = ["Researcher", "UnconfiguredResearcher", "TavilyResearcher"]
