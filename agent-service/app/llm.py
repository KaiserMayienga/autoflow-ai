"""LLM provider seam. Phase 1 uses rules only; Phase 2 adds Ollama/OpenRouter.

Contract for any provider: return schema-validated fields (extraction) or a
drafted explanation. It must never produce prices or change escalation.
"""
from typing import Protocol


class LLMProvider(Protocol):
    def extract(self, text: str) -> dict | None: ...


class RulesOnly:
    def extract(self, text: str) -> dict | None:
        return None  # nodes fall back to app.rules
