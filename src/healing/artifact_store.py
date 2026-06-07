"""
Artifact store — persists pipeline decision artifacts to tests/artifacts/.

Two entry points:
  emit_decision(decision, prefix) — generic writer for any ProvenanceRecord subclass.
  emit_artifacts(decision, timeline) — healing-specific writer (backward compat).

M2 decision (Phase 17 Stage 3): execution_timeline_*.json files are no longer written.
The streaming UI already renders the timeline live; the HealingDecision artifact
carries all decision-level data needed for later inspection.  emit_artifacts() keeps
its public signature so call-sites require no changes.
"""

import logging
from pathlib import Path

from schemas.healing import ExecutionTimeline, HealingDecision
from schemas.shared import ProvenanceRecord

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
ARTIFACTS_DIR = PROJECT_ROOT / "tests" / "artifacts"
ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)


def emit_decision(decision: ProvenanceRecord, prefix: str) -> Path:
    """Write any ProvenanceRecord subclass to a timestamped JSON artifact file.

    File name: ``{prefix}_YYYYMMDD_HHMMSS.json``

    Args:
        decision: Any decision object (HealingDecision, GenerationDecision, etc.).
        prefix:   Filename prefix, e.g. ``"healing_decision"`` or ``"vision_decision"``.

    Returns:
        Path to the written file.
    """
    from datetime import datetime

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = ARTIFACTS_DIR / f"{prefix}_{timestamp}.json"
    path.write_text(decision.model_dump_json(indent=2), encoding="utf-8")
    logger.info("Artifact saved: %s", path)
    return path


def emit_artifacts(decision: HealingDecision, timeline: ExecutionTimeline) -> None:
    """Write the healing decision artifact to tests/artifacts/.

    The ``timeline`` argument is accepted for backward-compatibility but is no
    longer written to disk; ``execution_timeline_*.json`` files were written-but-
    hidden (never surfaced in the UI) and the streaming timeline already shows
    the same information live.

    Args:
        decision: Completed HealingDecision to serialise.
        timeline: Ignored (kept for call-site backward compat).
    """
    emit_decision(decision, "healing_decision")
    logger.debug(
        "emit_artifacts: timeline not written (see Phase 17 Stage 3 M2 decision)"
    )
