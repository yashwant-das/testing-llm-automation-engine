"""
LLM router — central dispatch point for all LLM calls.

Responsibilities:
  - Provider and model selection (primary / vision / fallback)
  - Retry on transient failures with exponential backoff
  - Fallback to a secondary provider after primary exhausts retries
  - Structured logging: model, provider, latency_ms, input_tokens, output_tokens, retry_count

LLMRequest  — normalized chat completion request (Pydantic).
LLMResponse — normalized response with observability metadata (Pydantic).
LLMRouter   — orchestrator; use LLMRouter.from_env() for the standard setup.
"""

import logging
import os
import time
from typing import Optional

from openai import OpenAI
from pydantic import BaseModel, Field

from src.llm.client import LLMClientFactory, ProviderConfig
from src.llm.policies import RetryPolicy, TimeoutPolicy

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Request / Response schemas
# ---------------------------------------------------------------------------


class LLMRequest(BaseModel):
    """A normalized LLM chat completion request.

    The messages field follows the OpenAI messages format:
      [{"role": "system", "content": "..."}, {"role": "user", "content": "..."}]

    For vision calls the user content may be a list of dicts with
    {"type": "text", "text": "..."} and {"type": "image_url", ...} parts.
    """

    messages: list[dict] = Field(description="Chat messages in OpenAI format.")
    model: str = Field(description="Exact model identifier to use for this request.")
    temperature: float = Field(
        default=0.1,
        ge=0.0,
        le=2.0,
        description="Sampling temperature.",
    )
    max_tokens: Optional[int] = Field(
        default=None,
        gt=0,
        description="Maximum tokens in the response. None means provider default.",
    )


class LLMResponse(BaseModel):
    """A normalized LLM response with observability metadata.

    Every LLM call through LLMRouter returns this; callers read .content
    for the text and can inspect the rest for logging / tracing.
    """

    content: str = Field(description="Raw text content returned by the model.")
    model_used: str = Field(
        description="Actual model identifier reported by the provider."
    )
    provider: str = Field(description="Provider name that served this response.")
    latency_ms: int = Field(
        description="End-to-end call latency in milliseconds.", ge=0
    )
    input_tokens: int = Field(
        default=0, ge=0, description="Prompt token count (0 if not reported)."
    )
    output_tokens: int = Field(
        default=0, ge=0, description="Completion token count (0 if not reported)."
    )
    retry_count: int = Field(
        default=0, ge=0, description="Number of retries before success."
    )


# ---------------------------------------------------------------------------
# Router
# ---------------------------------------------------------------------------


class LLMRouter:
    """Routes LLM requests to the correct provider with retry and fallback.

    Args:
        primary_config:  ProviderConfig for the primary endpoint.
        primary_model:   Text/code model on the primary endpoint.
        vision_model:    Vision model on the primary endpoint. Defaults to primary_model
                         if not set (logs a warning on vision calls).
        fallback_config: Optional ProviderConfig for the fallback endpoint.
        fallback_model:  Text model on the fallback endpoint.
        retry_policy:    RetryPolicy — default is 3 retries with exponential backoff.
        timeout_policy:  TimeoutPolicy — default is 60 seconds per call.

    Usage:
        router = LLMRouter.from_env()
        response = router.complete_primary(messages=[...])
        print(response.content)
    """

    def __init__(
        self,
        primary_config: ProviderConfig,
        primary_model: str,
        vision_model: Optional[str] = None,
        fallback_config: Optional[ProviderConfig] = None,
        fallback_model: Optional[str] = None,
        retry_policy: Optional[RetryPolicy] = None,
        timeout_policy: Optional[TimeoutPolicy] = None,
    ) -> None:
        self._primary_config = primary_config
        self._primary_model = primary_model
        self._vision_model = vision_model or primary_model
        self._fallback_config = fallback_config
        self._fallback_model = fallback_model
        self._retry_policy = retry_policy or RetryPolicy()
        self._timeout_policy = timeout_policy or TimeoutPolicy()

        # Lazy client creation — OpenAI() is not called at __init__ time.
        self.__primary_client: Optional[OpenAI] = None
        self.__fallback_client: Optional[OpenAI] = None

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def primary_model(self) -> str:
        """Text/code model identifier for the primary provider."""
        return self._primary_model

    @property
    def vision_model(self) -> str:
        """Vision model identifier for the primary provider."""
        if self._vision_model == self._primary_model and self._vision_model:
            logger.debug(
                "No dedicated vision_model configured; using primary_model '%s' for vision calls.",
                self._primary_model,
            )
        return self._vision_model

    @property
    def _primary_client(self) -> OpenAI:
        """Lazily instantiated primary OpenAI client."""
        if self.__primary_client is None:
            self.__primary_client = LLMClientFactory.create(self._primary_config)
        return self.__primary_client

    @property
    def _fallback_client(self) -> Optional[OpenAI]:
        """Lazily instantiated fallback OpenAI client (None if not configured)."""
        if self._fallback_config and self.__fallback_client is None:
            self.__fallback_client = LLMClientFactory.create(self._fallback_config)
        return self.__fallback_client

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def complete(self, request: LLMRequest) -> LLMResponse:
        """Execute a chat completion with retry and fallback.

        Tries the primary provider up to retry_policy.total_attempts times.
        On exhaustion, falls back to the secondary provider if configured.

        Args:
            request: Normalized LLM request.

        Returns:
            LLMResponse with content and observability metadata.

        Raises:
            RuntimeError: If all attempts (primary + fallback) fail.
        """
        retry_count = 0
        last_exc: Optional[Exception] = None
        delay = self._retry_policy.initial_delay_seconds

        # --- Primary provider with retry ---
        for attempt in range(self._retry_policy.total_attempts):
            try:
                start = time.monotonic()
                completion = self._primary_client.chat.completions.create(
                    model=request.model,
                    messages=request.messages,
                    temperature=request.temperature,
                    **(
                        {"max_tokens": request.max_tokens} if request.max_tokens else {}
                    ),
                    timeout=self._timeout_policy.timeout_seconds,
                )
                latency_ms = int((time.monotonic() - start) * 1000)
                return self._build_response(
                    completion,
                    provider=self._primary_config.name,
                    latency_ms=latency_ms,
                    retry_count=retry_count,
                )

            except Exception as exc:
                last_exc = exc
                retry_count += 1

                if attempt < self._retry_policy.max_retries:
                    logger.warning(
                        "Primary LLM attempt %d/%d failed (model=%s): %s. Retrying in %.1fs…",
                        attempt + 1,
                        self._retry_policy.total_attempts,
                        request.model,
                        exc,
                        delay,
                    )
                    time.sleep(delay)
                    delay *= self._retry_policy.backoff_multiplier
                else:
                    logger.error(
                        "Primary LLM exhausted %d attempts (model=%s): %s",
                        self._retry_policy.total_attempts,
                        request.model,
                        exc,
                    )

        # --- Fallback provider (no retry on fallback — single attempt) ---
        if self._fallback_client is not None and self._fallback_model:
            fallback_provider = (
                self._fallback_config.name if self._fallback_config else "fallback"
            )
            logger.warning(
                "Falling back to %s/%s after primary exhausted retries.",
                fallback_provider,
                self._fallback_model,
            )
            try:
                start = time.monotonic()
                completion = self._fallback_client.chat.completions.create(
                    model=self._fallback_model,
                    messages=request.messages,
                    temperature=request.temperature,
                    **(
                        {"max_tokens": request.max_tokens} if request.max_tokens else {}
                    ),
                    timeout=self._timeout_policy.timeout_seconds,
                )
                latency_ms = int((time.monotonic() - start) * 1000)
                return self._build_response(
                    completion,
                    provider=fallback_provider,
                    latency_ms=latency_ms,
                    retry_count=retry_count,
                )
            except Exception as fallback_exc:
                raise RuntimeError(
                    f"Both primary ({request.model}) and fallback ({self._fallback_model}) LLMs failed. "
                    f"Primary error: {last_exc}. "
                    f"Fallback error: {fallback_exc}"
                ) from fallback_exc

        raise RuntimeError(
            f"LLM call failed after {self._retry_policy.total_attempts} attempt(s) "
            f"(model={request.model}, provider={self._primary_config.name}): {last_exc}"
        ) from last_exc

    def complete_primary(
        self,
        messages: list[dict],
        temperature: float = 0.1,
        max_tokens: Optional[int] = None,
    ) -> LLMResponse:
        """Convenience wrapper — calls complete() with the primary text model.

        Args:
            messages:    Chat messages in OpenAI format.
            temperature: Sampling temperature.
            max_tokens:  Response token limit (None = provider default).

        Returns:
            LLMResponse.
        """
        return self.complete(
            LLMRequest(
                messages=messages,
                model=self._primary_model,
                temperature=temperature,
                max_tokens=max_tokens,
            )
        )

    def complete_vision(
        self,
        messages: list[dict],
        temperature: float = 0.1,
        max_tokens: Optional[int] = None,
    ) -> LLMResponse:
        """Convenience wrapper — calls complete() with the vision model.

        Messages should include image_url content parts for vision inputs.

        Args:
            messages:    Chat messages in OpenAI format (may include image_url parts).
            temperature: Sampling temperature.
            max_tokens:  Response token limit (None = provider default).

        Returns:
            LLMResponse.
        """
        return self.complete(
            LLMRequest(
                messages=messages,
                model=self._vision_model,
                temperature=temperature,
                max_tokens=max_tokens,
            )
        )

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _build_response(
        self,
        completion,
        *,
        provider: str,
        latency_ms: int,
        retry_count: int,
    ) -> LLMResponse:
        """Build an LLMResponse from a raw OpenAI ChatCompletion.

        Falls back to the requested model name if the provider does not echo
        the model in the response (common with local servers).
        """
        content = ""
        if completion.choices and completion.choices[0].message.content:
            content = completion.choices[0].message.content

        # Local providers sometimes return None or "" for completion.model
        model_used = completion.model or "unknown"

        usage = completion.usage
        input_tokens = usage.prompt_tokens if usage else 0
        output_tokens = usage.completion_tokens if usage else 0

        logger.info(
            "LLM response: provider=%s model=%s latency=%dms "
            "input_tokens=%d output_tokens=%d retries=%d",
            provider,
            model_used,
            latency_ms,
            input_tokens,
            output_tokens,
            retry_count,
        )

        return LLMResponse(
            content=content,
            model_used=model_used,
            provider=provider,
            latency_ms=latency_ms,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            retry_count=retry_count,
        )

    # ------------------------------------------------------------------
    # Factory
    # ------------------------------------------------------------------

    @classmethod
    def from_env(cls) -> "LLMRouter":
        """Build a router from environment variables.

        Reads: LLM_PROVIDER, LM_STUDIO_URL, LM_STUDIO_MODEL, LM_STUDIO_VISION_MODEL,
               OLLAMA_URL, OLLAMA_MODEL, OLLAMA_VISION_MODEL.

        No fallback is configured by default; callers can construct the router
        directly if they need explicit fallback configuration.

        Returns:
            Configured LLMRouter instance.
        """
        provider = os.getenv("LLM_PROVIDER", "lm_studio").lower()
        primary_config = ProviderConfig.from_env(provider)

        if provider == "ollama":
            primary_model = os.getenv("OLLAMA_MODEL", "gemma4:26b")
            vision_model = os.getenv("OLLAMA_VISION_MODEL", "qwen3-vl:30b")
        else:
            primary_model = os.getenv("LM_STUDIO_MODEL", "qwen/qwen3-coder-30b")
            vision_model = os.getenv("LM_STUDIO_VISION_MODEL", "qwen/qwen3-vl-30b")

        return cls(
            primary_config=primary_config,
            primary_model=primary_model,
            vision_model=vision_model,
        )
