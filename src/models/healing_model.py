"""
Data models and schemas for the self-healing agent.

This module defines the structures for failure evidence, healing decisions,
and execution timelines used by the healing agent.
"""

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional


class FailureType(str, Enum):
    LOCATOR_NOT_FOUND = "LOCATOR_NOT_FOUND"
    LOCATOR_DRIFT = "LOCATOR_DRIFT"  # New: Element exists but attributes changed
    TIMEOUT = "TIMEOUT"
    ASSERTION_FAILED = "ASSERTION_FAILED"
    ENVIRONMENT_ISSUE = "ENVIRONMENT_ISSUE"  # New: Browser closed, network fail, etc.
    POTENTIAL_APP_DEFECT = "POTENTIAL_APP_DEFECT"  # New: Page blank, 500 error, etc.
    JAVASCRIPT_ERROR = "JAVASCRIPT_ERROR"
    UNKNOWN = "UNKNOWN"


@dataclass
class HealingAction:
    """Represents the specific code change applied."""

    original_code: str
    fixed_code: str
    description: str


@dataclass
class Evidence:
    """Collection of artifacts providing context for the failure."""

    error_log: str
    screenshot_path: Optional[str] = None
    dom_snippet: Optional[str] = None


@dataclass
class HealingDecision:
    """
    Structured record of a single healing attempt.
    """

    test_file: str
    failure_type: FailureType
    failure_summary: str
    evidence: Evidence
    hypothesis: str
    confidence_score: float
    reasoning_steps: List[str]
    action_taken: HealingAction
    verification_passed: bool = False
    verification_log: Optional[str] = None
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())

    def __post_init__(self):
        if isinstance(self.failure_type, str):
            try:
                self.failure_type = FailureType(self.failure_type)
            except ValueError:
                self.failure_type = FailureType.UNKNOWN

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), default=str, indent=2)

    def to_markdown(self) -> str:
        """Generate a human-readable markdown report."""
        emoji = "✅" if self.verification_passed else "❌"
        fail_type_str = (
            self.failure_type.value
            if hasattr(self.failure_type, "value")
            else str(self.failure_type)
        )
        return f"""
# Healing Report: {self.timestamp}
**File:** `{self.test_file}`
**Status:** {emoji} {"Fixed" if self.verification_passed else "Failed"}

## Diagnosis
- **Type:** `{fail_type_str}`
- **Summary:** {self.failure_summary}

## Evidence
- **Error:** `{self.evidence.error_log[:200]}...`
- **Screenshot:** `![Screenshot]({self.evidence.screenshot_path})`

## Resolution
**Hypothesis:** {self.hypothesis}
**Confidence:** {self.confidence_score}

**Reasoning:**
{chr(10).join([f"- {step}" for step in self.reasoning_steps])}

## Code Change
```typescript
// OLD
{self.action_taken.original_code}

// NEW
{self.action_taken.fixed_code}
```
"""


@dataclass
class TimelineStep:
    """A single step in the healing execution timeline."""

    step: str
    details: str
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())


@dataclass
class ExecutionTimeline:
    """Collection of steps representing the lifecycle of a healing attempt."""

    steps: List[TimelineStep] = field(default_factory=list)

    def add_step(self, step: str, details: str):
        """Add a new step to the timeline.

        Args:
            step: Name/category of the step
            details: Human-readable description of what happened
        """
        self.steps.append(TimelineStep(step=step, details=details))

    def to_json(self) -> str:
        """Serialize the timeline to a JSON string."""
        return json.dumps(asdict(self), default=str, indent=2)
