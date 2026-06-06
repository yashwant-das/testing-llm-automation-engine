"""
Pydantic schemas for the evaluation and benchmarking framework.

Stub for Phase 7. Defines the data contracts for benchmark runs and
evaluation results so the rest of the codebase can reference them
without depending on the (not-yet-built) benchmark runner.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, computed_field


class BenchmarkRunConfig(BaseModel):
    """
    Configuration for a single benchmark run.

    Every field is required for reproducibility: the same config + dataset
    must produce the same results at temperature 0 with a fixed seed.
    """

    model: str
    model_version: Optional[str] = None
    prompt_name: str
    prompt_version: str
    prompt_hash: str
    temperature: float = 0.0
    seed: Optional[int] = None
    dataset_version: str
    timestamp: str = Field(default_factory=lambda: datetime.now().isoformat())


class EvaluationResult(BaseModel):
    """Result of evaluating a single benchmark example."""

    example_id: str
    passed: bool
    score: float = Field(ge=0.0, le=1.0)
    details: Dict[str, Any] = Field(default_factory=dict)
    error: Optional[str] = None


class BenchmarkRun(BaseModel):
    """Aggregated results from a complete benchmark run."""

    config: BenchmarkRunConfig
    results: List[EvaluationResult] = Field(default_factory=list)

    @computed_field  # type: ignore[misc]
    @property
    def pass_rate(self) -> float:
        """Fraction of examples that passed."""
        if not self.results:
            return 0.0
        return sum(1 for r in self.results if r.passed) / len(self.results)

    @computed_field  # type: ignore[misc]
    @property
    def mean_score(self) -> float:
        """Mean score across all examples."""
        if not self.results:
            return 0.0
        return sum(r.score for r in self.results) / len(self.results)
