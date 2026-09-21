"""FastAPI dependencies."""

from __future__ import annotations

from functools import lru_cache

from app.core.config import Settings, get_settings
from app.core.store import get_store  # re-exported for routes
from app.llm.azure import AzureLLM
from app.llm.base import LLMClient
from app.llm.fake import FakeLLM

__all__ = ["get_store", "get_llm"]

def _build_llm(settings: Settings) -> LLMClient:
    if settings.llm_provider == "azure":
        return AzureLLM(settings)
    return FakeLLM()


@lru_cache
def get_llm() -> LLMClient:
    return _build_llm(get_settings())
