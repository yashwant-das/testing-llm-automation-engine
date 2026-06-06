"""
Shared types used across all schema modules.

This module provides the FailureType enum and RunResult model,
which are consumed by healing, generation, and evaluation schemas.
"""

from enum import Enum
from typing import Optional

from pydantic import BaseModel


class FailureType(str, Enum):
    """Classification of Playwright test failure types."""

    LOCATOR_NOT_FOUND = "LOCATOR_NOT_FOUND"
    LOCATOR_DRIFT = "LOCATOR_DRIFT"
    TIMEOUT = "TIMEOUT"
    ASSERTION_FAILED = "ASSERTION_FAILED"
    ENVIRONMENT_ISSUE = "ENVIRONMENT_ISSUE"
    POTENTIAL_APP_DEFECT = "POTENTIAL_APP_DEFECT"
    JAVASCRIPT_ERROR = "JAVASCRIPT_ERROR"
    UNKNOWN = "UNKNOWN"


class RunResult(BaseModel):
    """
    Result of a subprocess Playwright test run.

    Replaces the ad-hoc TestRunResult mock class in healer.py.
    Compatible with subprocess.CompletedProcess interface.
    """

    returncode: int
    stdout: str
    stderr: str

    @classmethod
    def from_timeout(
        cls, message: str = "Test execution timed out after 60 seconds"
    ) -> "RunResult":
        """Construct a failed RunResult representing a timeout."""
        return cls(returncode=1, stdout="", stderr=message)

    @classmethod
    def from_error(cls, message: str) -> "RunResult":
        """Construct a failed RunResult from an error message."""
        return cls(returncode=1, stdout="", stderr=message)

    @property
    def passed(self) -> bool:
        """True if the test run succeeded."""
        return self.returncode == 0

    @property
    def output(self) -> str:
        """Best available output string (stdout preferred over stderr)."""
        return self.stdout if self.stdout else self.stderr


class LLMConfig(BaseModel):
    """Configuration for a single LLM provider connection.

    Used by the LLM layer (Phase 2). Defined here to avoid circular imports.
    """

    provider: str  # "lm_studio" | "ollama" | "openai"
    base_url: Optional[str] = None
    api_key: Optional[str] = None
    model: str
    vision_model: Optional[str] = None
    temperature: float = 0.1
    seed: Optional[int] = None
