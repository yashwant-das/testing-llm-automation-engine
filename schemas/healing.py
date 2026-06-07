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
        "confidence_rationale": "Why this confidence level was chosen",
        "reasoning_steps": ["step 1", "step 2"],
        "root_cause_evidence": ["evidence item 1", "evidence item 2"],
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
    confidence_rationale: str = Field(
        default="",
        description="The LLM's explanation of why this confidence level was assigned.",
    )
    reasoning_steps: List[str]
    root_cause_evidence: List[str] = Field(
        default_factory=list,
        description="Specific evidence items from logs / DOM that support the diagnosis.",
    )
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
    Carries all provenance: test file, evidence, LLM analysis, verification,
    and explainability metadata (model used, prompt version, confidence rationale,
    root cause evidence).
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

    # Explainability fields — all default to empty / 0 so that
    # artifact JSON files produced before these fields existed remain valid.
    model_used: str = Field(
        default="",
        description="Model identifier that produced this decision (e.g. 'qwen3-coder-30b').",
    )
    prompt_version: str = Field(
        default="",
        description="Human-set version label from prompts/manifest.json (e.g. '2').",
    )
    prompt_hash: str = Field(
        default="",
        description="SHA-256 hex prefix of the healer prompt content at run time.",
    )
    confidence_rationale: str = Field(
        default="",
        description="LLM's explanation of why this confidence level was assigned.",
    )
    root_cause_evidence: List[str] = Field(
        default_factory=list,
        description="Specific evidence items from logs/DOM that support the diagnosis.",
    )
    execution_duration_ms: int = Field(
        default=0,
        ge=0,
        description="Wall-clock time for the full analyze_and_plan() call in milliseconds.",
    )
    context_snapshot_id: str = Field(
        default="",
        description="Short hash identifying the evidence error_log used for this decision.",
    )

    model_config = ConfigDict(use_enum_values=False)

    @classmethod
    def from_analysis(
        cls,
        *,
        test_file: str,
        analysis: HealingAnalysis,
        evidence: Evidence,
        model_used: str = "",
        prompt_version: str = "",
        prompt_hash: str = "",
        execution_duration_ms: int = 0,
        context_snapshot_id: str = "",
    ) -> "HealingDecision":
        """Construct a HealingDecision from a validated HealingAnalysis + evidence.

        Args:
            test_file:            Path to the failing test file.
            analysis:             Validated :class:`HealingAnalysis` from the LLM.
            evidence:             Evidence collected from the failure run.
            model_used:           Model identifier from :class:`~src.llm.router.LLMResponse`.
            prompt_version:       Version string from ``prompts/manifest.json``.
            prompt_hash:          SHA-256 hex prefix of the healer prompt.
            execution_duration_ms: Wall-clock time for the full planning call.
            context_snapshot_id:  Short hash of the evidence error_log.
        """
        return cls(
            test_file=test_file,
            failure_type=analysis.failure_type,
            failure_summary=analysis.failure_summary,
            evidence=evidence,
            hypothesis=analysis.hypothesis,
            confidence_score=analysis.confidence_score,
            confidence_rationale=analysis.confidence_rationale,
            reasoning_steps=analysis.reasoning_steps,
            root_cause_evidence=analysis.root_cause_evidence,
            action_taken=analysis.action_taken,
            model_used=model_used,
            prompt_version=prompt_version,
            prompt_hash=prompt_hash,
            execution_duration_ms=execution_duration_ms,
            context_snapshot_id=context_snapshot_id,
        )

    def to_dict(self) -> dict:
        """Return a JSON-serializable dict (enums as strings)."""
        return self.model_dump(mode="json")

    def to_json(self) -> str:
        """Serialize to a JSON string."""
        return self.model_dump_json(indent=2)

    def to_markdown(self) -> str:
        """Generate a human-readable markdown healing report.

        Includes Provenance and Root Cause Evidence sections so the artifact
        is self-explaining without needing to open the raw JSON.
        """
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

        model_str = self.model_used or "*(unknown)*"
        prompt_str = (
            f"`{self.prompt_version}` (hash: `{self.prompt_hash}`)"
            if self.prompt_version or self.prompt_hash
            else "*(unknown)*"
        )
        duration_str = (
            f"{self.execution_duration_ms} ms"
            if self.execution_duration_ms
            else "*(not recorded)*"
        )
        snapshot_str = (
            f"`{self.context_snapshot_id}`" if self.context_snapshot_id else "*(n/a)*"
        )

        if self.root_cause_evidence:
            rce_md = "\n".join(f"- {item}" for item in self.root_cause_evidence)
        else:
            rce_md = "*(none provided)*"

        rationale_md = self.confidence_rationale or "*(not provided)*"

        return f"""# Healing Report: {self.timestamp}

**File:** `{self.test_file}`
**Status:** {emoji} {"Fixed" if self.verification_passed else "Failed"}

## Diagnosis

- **Type:** `{fail_type_str}`
- **Summary:** {self.failure_summary}

## Evidence

- **Error:** `{self.evidence.error_log[:200]}...`
- **Screenshot:** {screenshot_md}

## Root Cause Evidence

{rce_md}

## Resolution

**Hypothesis:** {self.hypothesis}
**Confidence:** {self.confidence_score}

**Confidence Rationale:** {rationale_md}

**Reasoning:**

{steps_md}

## Code Change

```typescript
// OLD
{self.action_taken.original_code}

// NEW
{self.action_taken.fixed_code}
```

## Provenance

- **Model:** {model_str}
- **Prompt Version:** {prompt_str}
- **Execution Time:** {duration_str}
- **Context Snapshot:** {snapshot_str}
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
