"""
Artifact store — persists healing decision and execution timeline as JSON files.

Single responsibility: given a completed HealingDecision and ExecutionTimeline,
write two timestamped JSON files to ``tests/artifacts/``.  No LLM calls, no
subprocess calls.
"""

import logging
from datetime import datetime
from pathlib import Path

from schemas.healing import ExecutionTimeline, HealingDecision

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
ARTIFACTS_DIR = PROJECT_ROOT / "tests" / "artifacts"
ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)


def emit_artifacts(decision: HealingDecision, timeline: ExecutionTimeline) -> None:
    """Write the healing decision and execution timeline to JSON artifact files.

    File names follow the pattern:
      ``healing_decision_YYYYMMDD_HHMMSS.json``
      ``execution_timeline_YYYYMMDD_HHMMSS.json``

    Args:
        decision: Completed HealingDecision to serialise.
        timeline: Corresponding ExecutionTimeline to serialise.
    """
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    decision_path = ARTIFACTS_DIR / f"healing_decision_{timestamp}.json"
    decision_path.write_text(decision.to_json(), encoding="utf-8")

    timeline_path = ARTIFACTS_DIR / f"execution_timeline_{timestamp}.json"
    timeline_path.write_text(timeline.to_json(), encoding="utf-8")

    logger.info("Artifacts saved:\n     %s\n     %s", decision_path, timeline_path)
