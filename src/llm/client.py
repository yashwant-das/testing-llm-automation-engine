"""
LLM client factory — creates OpenAI-compatible clients with no module-level side effects.

ProviderConfig  — Pydantic model for a single provider endpoint.
LLMClientFactory — static factory; call create(config) to get an OpenAI client.
"""

import logging
import os

from openai import OpenAI
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class ProviderConfig(BaseModel):
    """Configuration for a single LLM provider endpoint."""

    name: str = Field(
        description="Human-readable provider name (e.g. 'lm_studio', 'ollama')."
    )
    base_url: str = Field(
        description="OpenAI-compatible base URL including /v1 suffix."
    )
    api_key: str = Field(
        default="lm-studio",
        description="API key (placeholder for local providers).",
    )

    @classmethod
    def for_lm_studio(cls) -> "ProviderConfig":
        """Build from LM Studio environment variables."""
        return cls(
            name="lm_studio",
            base_url=os.getenv("LM_STUDIO_URL", "http://localhost:1234/v1"),
            api_key=os.getenv("LM_STUDIO_API_KEY", "lm-studio"),
        )

    @classmethod
    def for_ollama(cls) -> "ProviderConfig":
        """Build from Ollama environment variables."""
        return cls(
            name="ollama",
            base_url=os.getenv("OLLAMA_URL", "http://localhost:11434/v1"),
            api_key="ollama",
        )

    @classmethod
    def from_env(cls, provider: str = "lm_studio") -> "ProviderConfig":
        """Build from environment variables for the named provider.

        Args:
            provider: 'lm_studio' or 'ollama'.

        Returns:
            ProviderConfig populated from environment.
        """
        if provider == "ollama":
            return cls.for_ollama()
        return cls.for_lm_studio()


class LLMClientFactory:
    """Creates OpenAI-compatible clients on demand.

    No module-level side effects — instantiation only happens when create() is called.
    """

    @staticmethod
    def create(config: ProviderConfig) -> OpenAI:
        """Create and return a configured OpenAI client.

        Args:
            config: Provider configuration.

        Returns:
            Configured OpenAI client instance. No network call is made here.
        """
        logger.debug(
            "Creating OpenAI client for provider '%s' at %s",
            config.name,
            config.base_url,
        )
        return OpenAI(base_url=config.base_url, api_key=config.api_key)

    @staticmethod
    def from_env(provider: str | None = None) -> OpenAI:
        """Convenience factory from environment variables.

        Args:
            provider: Provider name override. Reads LLM_PROVIDER env var if None.

        Returns:
            Configured OpenAI client instance.
        """
        resolved = provider or os.getenv("LLM_PROVIDER", "lm_studio").lower()
        config = ProviderConfig.from_env(resolved)
        return LLMClientFactory.create(config)
