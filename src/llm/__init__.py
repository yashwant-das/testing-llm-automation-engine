"""
LLM layer — factory, registry, router, and policies.

Public API
----------
LLMClientFactory   creates OpenAI clients on demand (no module-level side effects)
ModelCapabilities  capability descriptor for a registered model
ModelRegistry      model capability registry; call from_env() to populate
LLMRequest         normalized chat completion request (Pydantic)
LLMResponse        normalized response with observability metadata (Pydantic)
LLMRouter          central dispatch with retry, fallback, and structured logging
RetryPolicy        configurable retry with exponential backoff (Pydantic)
TimeoutPolicy      per-call timeout configuration (Pydantic)
ProviderConfig     provider endpoint configuration (Pydantic)

Convenience
-----------
get_default_router()  returns the module-level lazily initialised LLMRouter

Example
-------
    from src.llm import get_default_router

    router = get_default_router()
    response = router.complete_primary(messages=[
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user",   "content": "Write a hello-world Playwright test."},
    ])
    print(response.content)
    print(f"Took {response.latency_ms}ms, {response.output_tokens} tokens")
"""

from __future__ import annotations

from typing import Optional

from src.llm.client import LLMClientFactory, ProviderConfig
from src.llm.policies import RetryPolicy, TimeoutPolicy
from src.llm.registry import ModelCapabilities, ModelRegistry
from src.llm.router import LLMRequest, LLMResponse, LLMRouter

# ---------------------------------------------------------------------------
# Module-level lazy singleton — no OpenAI() call at import time.
# ---------------------------------------------------------------------------

_default_router: Optional[LLMRouter] = None


def get_default_router() -> LLMRouter:
    """Return the default LLMRouter, building it from environment variables on first call.

    The singleton is created lazily — no side effects at import time.
    The underlying OpenAI client is itself lazy; the first actual network call
    happens when complete() is called.

    Returns:
        The shared LLMRouter instance for this process.
    """
    global _default_router
    if _default_router is None:
        _default_router = LLMRouter.from_env()
    return _default_router


def _reset_default_router_for_testing() -> None:
    """Reset the module-level router singleton.

    For use in unit tests that need to construct the router under
    different environment variable conditions.  Not part of the public API.
    """
    global _default_router
    _default_router = None


__all__ = [
    "LLMClientFactory",
    "LLMRequest",
    "LLMResponse",
    "LLMRouter",
    "ModelCapabilities",
    "ModelRegistry",
    "ProviderConfig",
    "RetryPolicy",
    "TimeoutPolicy",
    "get_default_router",
]
