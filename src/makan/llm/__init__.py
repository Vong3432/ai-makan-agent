"""LLM layer: provider interface, implementations, agent jobs."""

from makan.config import Settings, get_settings
from makan.llm.base import LLMError, LLMProvider


def get_llm(settings: Settings | None = None) -> LLMProvider:
    from makan.llm.anthropic_provider import AnthropicProvider

    return AnthropicProvider(settings or get_settings())


__all__ = ["LLMError", "LLMProvider", "get_llm"]
