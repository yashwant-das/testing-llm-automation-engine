"""
Pydantic schemas for the healing pipeline.

Two distinct models serve different purposes:

  HealingAnalysis  — what the LLM must return (the structured output contract).
  HealingDecision  — the complete artifact record written to tests/artifacts/.

Keeping them separate lets the LLM schema stay minimal while the artifact
schema carries all provenance metadata (test file, evidence, timestamps,
verification results).
"""

from datetime import datetime
from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

from .artifacts import ContextSnapshot
from .shared import FailureType


class RepairStrategy(str, Enum):
    """Repair strategy selected by the LLM for each HealingAction.

    The planner chooses the strategy most appropriate for the failure type.
    ``string_replace`` is the legacy fallback; all other values trigger the
    ts-morph AST repair path in ``src/healing/repair.py``.

    | Value              | What the AST script does |
    |--------------------|--------------------------|
    | string_replace     | Existing sliding-window string replacement (fallback) |
    | selector_replace   | Find all matching locator/getByX calls and replace the selector argument |
    | import_add         | Insert a missing import declaration (skips if already present) |
    | timeout_adjust     | Find ``{ timeout: N }`` properties and update the value |
    | role_argument      | Update the ``name`` option in a ``getByRole()`` call |
    | assertion_swap     | Rename an assertion method in an ``expect()`` chain |
    """

    STRING_REPLACE = "string_replace"
    SELECTOR_REPLACE = "selector_replace"
    IMPORT_ADD = "import_add"
    TIMEOUT_ADJUST = "timeout_adjust"
    ROLE_ARGUMENT = "role_argument"
    ASSERTION_SWAP = "assertion_swap"


class HealingAction(BaseModel):
    """The specific code change proposed or applied during healing."""

    original_code: str
    fixed_code: str
    description: str
    repair_strategy: RepairStrategy = Field(default=RepairStrategy.STRING_REPLACE)

    @field_validator("original_code", "fixed_code", mode="before")
    @classmethod
    def coerce_list_to_str(cls, v: object) -> str:
        """Accept list-of-lines from LLM (common failure mode) and join them."""
        if isinstance(v, list):
            return "\n".join(str(line) for line in v)
        return str(v) if v is not None else ""

    @field_validator("repair_strategy", mode="before")
    @classmethod
    def coerce_repair_strategy(cls, v: object) -> RepairStrategy:
        """Accept None or missing field from older LLM responses."""
        if v is None:
            return RepairStrategy.STRING_REPLACE
        return v


class Evidence(BaseModel):
    """Artifacts collected from a failed test run to support diagnosis."""

    error_log: str
    screenshot_path: Optional[str] = None
    dom_snippet: Optional[str] = None
    # Phase 6: extended context from context collector
    console_errors: List[str] = Field(default_factory=list)
    network_errors: List[str] = Field(default_factory=list)
    accessibility_tree: Optional[str] = None
    locator_candidates: List[str] = Field(default_factory=list)

    @classmethod
    def from_context_snapshot(
        cls,
        error_log: str,
        snapshot: ContextSnapshot,
        *,
        screenshot_path: Optional[str] = None,
    ) -> "Evidence":
        """Create Evidence from a ContextSnapshot plus error logs.

        Args:
            error_log:       Raw error output from the failing test run.
            snapshot:        ContextSnapshot collected from the target URL.
            screenshot_path: Path to a Playwright failure screenshot.  Takes
                             precedence over any screenshot in the snapshot.

        Returns:
            Evidence populated with all available context fields.
        """
        return cls(
            error_log=error_log,
            screenshot_path=screenshot_path or snapshot.screenshot_path,
            dom_snippet=snapshot.html,
            console_errors=list(snapshot.console_errors),
            network_errors=list(snapshot.network_errors),
            accessibility_tree=snapshot.accessibility_tree,
            locator_candidates=list(snapshot.locator_candidates),
        )


class HealingAnalysis(BaseModel):
    """
    LLM response schema for healer analysis.

    This is the structured output contract: every field the LLM must produce.
    Pydantic validates the response before any field is accessed. If validation
    fails, the caller retries or falls back — no silent data corruption.

    JSON schema for the healer prompt:
    {
        "failure_type": "LOCATOR_DRIFT | TIMEOUT | ASSERTION_FAILED | ...",
        "failure_summary": "Short description of failure",
        "hypothesis": "Why the fix will work",
        "confidence_score": 0.95,
        "reasoning_steps": ["step 1", "step 2"],
        "action_taken": {
            "original_code": "exact contiguous block to replace",
            "fixed_code": "replacement block",
            "description": "what changed",
            "repair_strategy": "string_replace | selector_replace | import_add | timeout_adjust | role_argument | assertion_swap"
        }
    }
    """

    failure_type: FailureType
    failure_summary: str
    hypothesis: str
    confidence_score: float = Field(ge=0.0, le=1.0)
    reasoning_steps: List[str]
    action_taken: HealingAction

    model_config = ConfigDict(use_enum_values=False)

    @field_validator("confidence_score", mode="before")
    @classmethod
    def clamp_confidence(cls, v: object) -> float:
        """Clamp to [0, 1] — LLMs occasionally return 1.05 etc."""
        return max(0.0, min(1.0, float(v)))

    @field_validator("reasoning_steps", mode="before")
    @classmethod
    def coerce_single_step(cls, v: object) -> List[str]:
        """Accept a bare string when LLM returns one step instead of a list."""
        if isinstance(v, str):
            return [v]
        return list(v) if v else []


class HealingDecision(BaseModel):
    """
    Full artifact record of a single healing attempt.

    Written to tests/artifacts/ as JSON after every healing session.
    Carries all provenance: test file, evidence, LLM analysis, verification.
    """

    test_file: str
    failure_type: FailureType
    failure_summary: str
    evidence: Evidence
    hypothesis: str
    confidence_score: float = Field(ge=0.0, le=1.0)
    reasoning_steps: List[str]
    action_taken: HealingAction
    verification_passed: bool = False
    verification_log: Optional[str] = None
    timestamp: str = Field(default_factory=lambda: datetime.now().isoformat())

    model_config = ConfigDict(use_enum_values=False)

    @classmethod
    def from_analysis(
        cls,
        *,
        test_file: str,
        analysis: HealingAnalysis,
        evidence: Evidence,
    ) -> "HealingDecision":
        """Construct a HealingDecision from a validated HealingAnalysis + evidence."""
        return cls(
            test_file=test_file,
            failure_type=analysis.failure_type,
            failure_summary=analysis.failure_summary,
            evidence=evidence,
            hypothesis=analysis.hypothesis,
            confidence_score=analysis.confidence_score,
            reasoning_steps=analysis.reasoning_steps,
            action_taken=analysis.action_taken,
        )

    def to_dict(self) -> dict:
        """Return a JSON-serializable dict (enums as strings)."""
        return self.model_dump(mode="json")

    def to_json(self) -> str:
        """Serialize to a JSON string."""
        return self.model_dump_json(indent=2)

    def to_markdown(self) -> str:
        """Generate a human-readable markdown healing report."""
        emoji = "✅" if self.verification_passed else "❌"
        fail_type_str = (
            self.failure_type.value
            if hasattr(self.failure_type, "value")
            else str(self.failure_type)
        )
        steps_md = "\n".join(f"- {step}" for step in self.reasoning_steps)
        screenshot_md = (
            f"![Screenshot]({self.evidence.screenshot_path})"
            if self.evidence.screenshot_path
            else "*(no screenshot)*"
        )
        return f"""# Healing Report: {self.timestamp}
**File:** `{self.test_file}`
**Status:** {emoji} {"Fixed" if self.verification_passed else "Failed"}

## Diagnosis
- **Type:** `{fail_type_str}`
- **Summary:** {self.failure_summary}

## Evidence
- **Error:** `{self.evidence.error_log[:200]}...`
- **Screenshot:** {screenshot_md}

## Resolution
**Hypothesis:** {self.hypothesis}
**Confidence:** {self.confidence_score}

**Reasoning:**
{steps_md}

## Code Change
```typescript
// OLD
{self.action_taken.original_code}

// NEW
{self.action_taken.fixed_code}
```
"""


class TimelineStep(BaseModel):
    """A single timestamped step in the healing execution timeline."""

    step: str
    details: str
    timestamp: str = Field(default_factory=lambda: datetime.now().isoformat())


class ExecutionTimeline(BaseModel):
    """Ordered audit trail of steps executed during a healing session."""

    steps: List[TimelineStep] = Field(default_factory=list)

    def add_step(self, step: str, details: str) -> None:
        """Append a new timestamped step."""
        self.steps.append(TimelineStep(step=step, details=details))

    def to_json(self) -> str:
        """Serialize to a JSON string."""
        return self.model_dump_json(indent=2)
