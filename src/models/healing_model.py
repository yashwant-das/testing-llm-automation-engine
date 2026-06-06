"""
Backward-compatibility shim for src/models/healing_model.

All types have been migrated to schemas/healing.py (Pydantic BaseModel).
This module re-exports them so existing imports continue to work during
the transition.  It will be deleted once all callers are updated to import
from `schemas` directly (targeted for Phase 4 cleanup).
"""

from schemas.healing import (  # noqa: F401
    Evidence,
    ExecutionTimeline,
    HealingAction,
    HealingAnalysis,
    HealingDecision,
    TimelineStep,
)
from schemas.shared import FailureType  # noqa: F401

__all__ = [
    "FailureType",
    "Evidence",
    "HealingAction",
    "HealingAnalysis",
    "HealingDecision",
    "TimelineStep",
    "ExecutionTimeline",
]
