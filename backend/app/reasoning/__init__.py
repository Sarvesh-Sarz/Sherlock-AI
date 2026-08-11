"""Reasoning layer — turns a case's evidence and research into an
`InvestigationReport` (see `app.models.investigation_report`).

`Reasoner` (see `reasoner.py`) is the model-agnostic interface.
`BaselineReasoner` (see `baseline_reasoner.py`) is the deterministic,
rule-based implementation. `OllamaReasoner` (see `ollama_reasoner.py`)
is a local-LLM-backed implementation. `FallbackReasoner` (see
`fallback_reasoner.py`) composes the two — tries the LLM, falls back to
the baseline if it's unreachable or its output can't be trusted — which
is what `app.api.deps.get_reasoner` wires up by default.

`signals.py` and `query_builder.py` are internal helpers
`BaselineReasoner` and the investigation service's research step share,
so "what evidence is worth acting on" is defined in exactly one place.
"""

from app.reasoning.baseline_reasoner import BaselineReasoner
from app.reasoning.fallback_reasoner import FallbackReasoner
from app.reasoning.ollama_reasoner import OllamaReasoner
from app.reasoning.reasoner import Reasoner

__all__ = ["Reasoner", "BaselineReasoner", "OllamaReasoner", "FallbackReasoner"]
