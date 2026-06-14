"""
Retry and timeout policies for LLM calls.

RetryPolicy   — configurable exponential-backoff retry with max attempt count.
TimeoutPolicy — per-call timeout passed through to the OpenAI client.
"""

from pydantic import BaseModel, Field


class RetryPolicy(BaseModel):
    """Configuration for retry-on-failure behaviour.

    Used by LLMRouter.complete() — this is a pure data model; the execution
    logic lives in the router.

    Attributes:
        max_retries:          Maximum number of retries after the first attempt.
                              0 means no retries (single attempt only).
        initial_delay_seconds: Delay before the first retry.
        backoff_multiplier:   Factor applied to the delay after each retry.
                              2.0 means 1s, 2s, 4s, …

    Example (default — 3 retries with exponential backoff):
        policy = RetryPolicy()
        # Attempts: t=0, t+1s, t+3s, t+7s (4 total attempts)
    """

    max_retries: int = Field(
        default=3,
        ge=0,
        description="Maximum number of retries after the initial attempt.",
    )
    initial_delay_seconds: float = Field(
        default=1.0,
        gt=0,
        description="Seconds to wait before the first retry.",
    )
    backoff_multiplier: float = Field(
        default=2.0,
        ge=1.0,
        description="Multiplier applied to the delay after each retry.",
    )

    @property
    def total_attempts(self) -> int:
        """Total number of call attempts (initial + retries)."""
        return self.max_retries + 1


class TimeoutPolicy(BaseModel):
    """Per-call timeout configuration.

    Passed directly to the OpenAI client's timeout parameter.

    Attributes:
        timeout_seconds: Maximum seconds to wait for a single LLM API call.
    """

    timeout_seconds: int = Field(
        default=60,
        gt=0,
        description="Maximum seconds to wait for a single LLM API call.",
    )
