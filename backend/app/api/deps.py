"""FastAPI dependencies.

`get_llm` returns `FakeLLM` until C4 provides the real adapter; swap the body
here (or override in tests) — no route code changes.
"""

from __future__ import annotations

from app.core.store import get_store  # re-exported for routes
from app.llm.base import LLMClient
from app.llm.fake import FakeLLM

__all__ = ["get_store", "get_llm"]

_LLM: LLMClient = FakeLLM()


def get_llm() -> LLMClient:
    return _LLM
