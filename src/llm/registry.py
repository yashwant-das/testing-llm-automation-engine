"""
Model registry with capability metadata.

ModelCapabilities — Pydantic model describing what a model can do.
ModelRegistry     — Class-level registry; call from_env() to populate from environment.
"""

import logging
import os
from typing import ClassVar

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class ModelCapabilities(BaseModel):
    """Capabilities and metadata for a registered model."""

    model_id: str = Field(description="Exact model identifier used in API calls.")
    provider: str = Field(description="Provider name (e.g. 'lm_studio', 'ollama').")
    is_vision_capable: bool = Field(
        default=False,
        description="True if the model accepts image_url content in messages.",
    )
    context_window: int = Field(
        default=8192,
        description="Maximum context window in tokens.",
        gt=0,
    )
    description: str = Field(
        default="", description="Optional human-readable description."
    )


class ModelRegistry:
    """Registry of known models and their capabilities.

    Usage:
        ModelRegistry.from_env()                    # populate from environment
        caps = ModelRegistry.get("qwen/qwen3-coder-30b")
        all_models = ModelRegistry.all_models()
    """

    _models: ClassVar[dict[str, ModelCapabilities]] = {}

    @classmethod
    def register(cls, capabilities: ModelCapabilities) -> None:
        """Register a model's capabilities.

        Args:
            capabilities: Model capabilities descriptor.
        """
        cls._models[capabilities.model_id] = capabilities
        logger.debug(
            "Registered model: %s (provider=%s)",
            capabilities.model_id,
            capabilities.provider,
        )

    @classmethod
    def get(cls, model_id: str) -> ModelCapabilities | None:
        """Retrieve capabilities for a model.

        Args:
            model_id: Exact model identifier.

        Returns:
            ModelCapabilities if registered, None otherwise.
        """
        return cls._models.get(model_id)

    @classmethod
    def is_vision_capable(cls, model_id: str) -> bool:
        """Check whether a model supports vision inputs.

        Returns False for unregistered models (conservative default).
        """
        caps = cls._models.get(model_id)
        return caps.is_vision_capable if caps else False

    @classmethod
    def all_models(cls) -> list[ModelCapabilities]:
        """Return all registered model descriptors."""
        return list(cls._models.values())

    @classmethod
    def clear(cls) -> None:
        """Clear all registered models (used in tests)."""
        cls._models.clear()

    @classmethod
    def from_env(cls) -> "ModelRegistry":
        """Populate the registry from environment variables.

        Registers both text and vision models for all configured providers.

        Returns:
            The ModelRegistry class (populated in place).
        """
        lm_studio_model = os.getenv("LM_STUDIO_MODEL", "qwen/qwen3-coder-30b")
        lm_studio_vision = os.getenv("LM_STUDIO_VISION_MODEL", "qwen/qwen3-vl-30b")
        ollama_model = os.getenv("OLLAMA_MODEL", "gemma4:26b")
        ollama_vision = os.getenv("OLLAMA_VISION_MODEL", "qwen3-vl:30b")

        cls.register(
            ModelCapabilities(
                model_id=lm_studio_model,
                provider="lm_studio",
                is_vision_capable=False,
                description="LM Studio primary text model",
            )
        )
        cls.register(
            ModelCapabilities(
                model_id=lm_studio_vision,
                provider="lm_studio",
                is_vision_capable=True,
                description="LM Studio vision model",
            )
        )
        cls.register(
            ModelCapabilities(
                model_id=ollama_model,
                provider="ollama",
                is_vision_capable=False,
                description="Ollama primary text model",
            )
        )
        cls.register(
            ModelCapabilities(
                model_id=ollama_vision,
                provider="ollama",
                is_vision_capable=True,
                description="Ollama vision model",
            )
        )

        logger.debug(
            "ModelRegistry populated with %d models from environment", len(cls._models)
        )
        return cls()
