"""
Pydantic schemas for the evaluation and benchmarking framework.

Phase 7: Defines the data contracts for benchmark runs and evaluation results.
These schemas are shared by generation, healing, and intent-validation runners.
"""

from datetime import datetime
from pathlib import Path
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
    provider: str = "unknown"
    prompt_name: str
    prompt_version: str
    prompt_hash: str
    temperature: float = 0.0
    seed: Optional[int] = None
    dataset_version: str
    benchmark_type: str = "unknown"  # "generation" | "healing" | "intent_validation"
    timestamp: str = Field(default_factory=lambda: datetime.now().isoformat())


class EvaluationResult(BaseModel):
    """Result of evaluating a single benchmark example."""

    example_id: str
    passed: bool
    score: float = Field(ge=0.0, le=1.0)
    duration_ms: int = 0
    details: Dict[str, Any] = Field(default_factory=dict)
    error: Optional[str] = None


class BenchmarkRun(BaseModel):
    """Aggregated results from a complete benchmark run."""

    config: BenchmarkRunConfig
    results: List[EvaluationResult] = Field(default_factory=list)

    @computed_field  # type: ignore[misc]
    @property
    def total(self) -> int:
        """Total number of examples evaluated."""
        return len(self.results)

    @computed_field  # type: ignore[misc]
    @property
    def passed(self) -> int:
        """Number of examples that passed."""
        return sum(1 for r in self.results if r.passed)

    @computed_field  # type: ignore[misc]
    @property
    def failed(self) -> int:
        """Number of examples that failed."""
        return sum(1 for r in self.results if not r.passed)

    @computed_field  # type: ignore[misc]
    @property
    def pass_rate(self) -> float:
        """Fraction of examples that passed (0.0–1.0)."""
        if not self.results:
            return 0.0
        return self.passed / self.total

    @computed_field  # type: ignore[misc]
    @property
    def mean_score(self) -> float:
        """Mean score across all examples (0.0–1.0)."""
        if not self.results:
            return 0.0
        return sum(r.score for r in self.results) / self.total

    @computed_field  # type: ignore[misc]
    @property
    def mean_duration_ms(self) -> float:
        """Mean per-example duration in milliseconds."""
        if not self.results:
            return 0.0
        return sum(r.duration_ms for r in self.results) / self.total

    def to_json(self, indent: int = 2) -> str:
        """Serialize to a JSON string (computed fields included)."""
        return self.model_dump_json(indent=indent)

    def save_report(
        self,
        output_dir: Path,
        filename: Optional[str] = None,
    ) -> Path:
        """Write the report JSON to output_dir and return the path.

        Args:
            output_dir: Directory to write the report.  Created if absent.
            filename:   Override the auto-generated filename.

        Returns:
            Absolute path to the saved JSON file.
        """
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        if filename is None:
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            btype = self.config.benchmark_type or "benchmark"
            model_slug = self.config.model.replace("/", "_").replace(":", "_")
            filename = f"{btype}_{model_slug}_{ts}.json"

        path = output_dir / filename
        path.write_text(self.to_json(), encoding="utf-8")
        return path
