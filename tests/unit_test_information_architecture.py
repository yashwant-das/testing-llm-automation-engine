"""
Stage 5 — Information architecture unit tests.

Covers:
  get_system_overview()        — static markdown for the Overview tab
  load_run_history()           — unified cross-pipeline run table
  load_most_recent_artifact()  — IA-4 auto-populate for Artifact Inspector
"""

import json
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


PROJECT_ROOT = Path(__file__).resolve().parent.parent
_ARTIFACTS_DIR = PROJECT_ROOT / "tests" / "artifacts"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _write_healing_artifact(
    artifacts_dir: Path, name: str, *, passed: bool = True, trace_id: str = ""
) -> None:
    """Write a minimal healing_decision JSON to artifacts_dir."""
    data = {
        "timestamp": "2026-06-07T12:00:00",
        "model_used": "mock-model",
        "provider": "local",
        "prompt_version": "1",
        "prompt_hash": "abc123",
        "input_tokens": 10,
        "output_tokens": 20,
        "latency_ms": 100,
        "retry_count": 0,
        "trace_id": trace_id,
        "context_snapshot_id": "",
        "test_file": "test_example.ts",
        "failure_type": "LOCATOR_DRIFT",
        "failure_summary": "Locator drifted",
        "evidence": {
            "error_log": "Error: locator not found",
            "screenshot_path": None,
            "dom_snippet": None,
            "console_errors": [],
            "network_errors": [],
            "accessibility_tree": None,
            "locator_candidates": [],
        },
        "hypothesis": "The locator changed.",
        "confidence_score": 0.9,
        "reasoning_steps": ["Step 1"],
        "action_taken": {
            "original_code": "old",
            "fixed_code": "new",
            "description": "fixed",
            "repair_strategy": "selector_replace",
        },
        "verification_passed": passed,
        "verification_log": None,
        "confidence_rationale": "",
        "root_cause_evidence": [],
        "execution_duration_ms": 0,
    }
    (artifacts_dir / name).write_text(json.dumps(data), encoding="utf-8")


def _write_generation_artifact(artifacts_dir: Path, name: str) -> None:
    """Write a minimal generation_decision JSON to artifacts_dir."""
    data = {
        "timestamp": "2026-06-07T13:00:00",
        "model_used": "gen-model",
        "provider": "local",
        "prompt_version": "1",
        "prompt_hash": "def456",
        "input_tokens": 5,
        "output_tokens": 50,
        "latency_ms": 200,
        "retry_count": 0,
        "trace_id": "",
        "context_snapshot_id": "",
        "url": "https://example.com",
        "feature_description": "login",
        "code": "test('login', () => {});",
        "context_snapshot": None,
    }
    (artifacts_dir / name).write_text(json.dumps(data), encoding="utf-8")


# ---------------------------------------------------------------------------
# TestGetSystemOverview
# ---------------------------------------------------------------------------


class TestGetSystemOverview(unittest.TestCase):
    """get_system_overview() returns comprehensive static markdown."""

    def setUp(self):
        from src.services.workbench_service import get_system_overview

        self.overview = get_system_overview()

    def test_returns_string(self):
        self.assertIsInstance(self.overview, str)

    def test_not_empty(self):
        self.assertGreater(len(self.overview), 100)

    def test_mentions_pipelines(self):
        self.assertIn("Pipeline", self.overview)

    def test_mentions_artifact_inspector(self):
        self.assertIn("Artifact Inspector", self.overview)

    def test_mentions_generation_healing_vision(self):
        self.assertIn("Generation", self.overview)
        self.assertIn("Healing", self.overview)
        self.assertIn("Vision", self.overview)

    def test_mentions_engineering_surfaces(self):
        self.assertIn("Evaluation", self.overview)
        self.assertIn("Trace Inspector", self.overview)
        self.assertIn("Models", self.overview)

    def test_has_navigation_guide(self):
        self.assertIn("Navigation", self.overview)


# ---------------------------------------------------------------------------
# TestLoadRunHistory
# ---------------------------------------------------------------------------


class TestLoadRunHistory(unittest.TestCase):
    """load_run_history() returns a unified cross-pipeline table."""

    def test_no_artifacts_dir_returns_placeholder(self):
        absent = Path("/tmp/_nonexistent_artifacts_stage5_ia_test")
        with patch("src.services.workbench_service._ARTIFACTS_DIR", absent):
            from src.services.workbench_service import load_run_history

            md = load_run_history()
        self.assertIn("not found", md.lower())

    def test_empty_artifacts_dir_returns_placeholder(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch("src.services.workbench_service._ARTIFACTS_DIR", Path(tmpdir)):
                from src.services.workbench_service import load_run_history

                md = load_run_history()
        self.assertIn("No decision artifacts", md)

    def test_single_healing_artifact_appears_in_table(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            td = Path(tmpdir)
            _write_healing_artifact(td, "healing_decision_001.json", passed=True)
            with patch("src.services.workbench_service._ARTIFACTS_DIR", td):
                from src.services.workbench_service import load_run_history

                md = load_run_history()
        self.assertIn("## Recent Runs", md)
        self.assertIn("Healing", md)
        self.assertIn("healing_decision_001.json", md)

    def test_generation_artifact_appears_as_generation(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            td = Path(tmpdir)
            _write_generation_artifact(td, "generation_decision_001.json")
            with patch("src.services.workbench_service._ARTIFACTS_DIR", td):
                from src.services.workbench_service import load_run_history

                md = load_run_history()
        self.assertIn("Generation", md)
        self.assertIn("generation_decision_001.json", md)

    def test_healing_passed_shows_healed_status(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            td = Path(tmpdir)
            _write_healing_artifact(td, "healing_decision_pass.json", passed=True)
            with patch("src.services.workbench_service._ARTIFACTS_DIR", td):
                from src.services.workbench_service import load_run_history

                md = load_run_history()
        self.assertIn("Healed", md)

    def test_healing_failed_shows_failed_status(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            td = Path(tmpdir)
            _write_healing_artifact(td, "healing_decision_fail.json", passed=False)
            with patch("src.services.workbench_service._ARTIFACTS_DIR", td):
                from src.services.workbench_service import load_run_history

                md = load_run_history()
        self.assertIn("Failed", md)

    def test_table_headers_present(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            td = Path(tmpdir)
            _write_healing_artifact(td, "healing_decision_001.json")
            with patch("src.services.workbench_service._ARTIFACTS_DIR", td):
                from src.services.workbench_service import load_run_history

                md = load_run_history()
        self.assertIn("| Timestamp |", md)
        self.assertIn("| Pipeline |", md)
        self.assertIn("| Artifact |", md)

    def test_trace_id_truncated_in_table(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            td = Path(tmpdir)
            _write_healing_artifact(
                td, "healing_decision_trace.json", trace_id="abcdef1234567890"
            )
            with patch("src.services.workbench_service._ARTIFACTS_DIR", td):
                from src.services.workbench_service import load_run_history

                md = load_run_history()
        self.assertIn("abcdef12", md)  # first 8 chars
        self.assertIn("…", md)

    def test_corrupted_artifact_skipped_gracefully(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            td = Path(tmpdir)
            (td / "healing_decision_bad.json").write_text("not-json", encoding="utf-8")
            _write_healing_artifact(td, "healing_decision_good.json")
            with patch("src.services.workbench_service._ARTIFACTS_DIR", td):
                from src.services.workbench_service import load_run_history

                md = load_run_history()
        self.assertIn("healing_decision_good.json", md)

    def test_limit_respected(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            td = Path(tmpdir)
            for i in range(5):
                _write_healing_artifact(td, f"healing_decision_{i:03d}.json")
                time.sleep(0.01)
            with patch("src.services.workbench_service._ARTIFACTS_DIR", td):
                from src.services.workbench_service import load_run_history

                md = load_run_history(limit=3)
        rows = [line for line in md.splitlines() if line.startswith("| 2026")]
        self.assertLessEqual(len(rows), 3)

    def test_mixed_pipeline_types_all_shown(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            td = Path(tmpdir)
            _write_healing_artifact(td, "healing_decision_x.json")
            _write_generation_artifact(td, "generation_decision_x.json")
            with patch("src.services.workbench_service._ARTIFACTS_DIR", td):
                from src.services.workbench_service import load_run_history

                md = load_run_history()
        self.assertIn("Healing", md)
        self.assertIn("Generation", md)


# ---------------------------------------------------------------------------
# TestLoadMostRecentArtifact
# ---------------------------------------------------------------------------


class TestLoadMostRecentArtifact(unittest.TestCase):
    """load_most_recent_artifact() returns the newest artifact for IA-4."""

    def test_no_artifacts_returns_placeholder_tuple(self):
        absent = Path("/tmp/_nonexistent_artifacts_stage5_ia_mra")
        with patch("src.services.workbench_service._ARTIFACTS_DIR", absent):
            from src.services.workbench_service import load_most_recent_artifact

            md, raw = load_most_recent_artifact()
        self.assertIsInstance(md, str)
        self.assertIsInstance(raw, dict)
        self.assertIn("No artifacts", md)

    def test_returns_markdown_and_dict_tuple(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            td = Path(tmpdir)
            _write_healing_artifact(td, "healing_decision_newest.json")
            with patch("src.services.workbench_service._ARTIFACTS_DIR", td):
                from src.services.workbench_service import load_most_recent_artifact

                md, raw = load_most_recent_artifact()
        self.assertIsInstance(md, str)
        self.assertIsInstance(raw, dict)

    def test_returns_most_recently_modified_artifact(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            td = Path(tmpdir)
            _write_healing_artifact(td, "healing_decision_old.json", passed=False)
            time.sleep(0.02)
            _write_healing_artifact(td, "healing_decision_new.json", passed=True)
            with patch("src.services.workbench_service._ARTIFACTS_DIR", td):
                from src.services.workbench_service import load_most_recent_artifact

                md, raw = load_most_recent_artifact()
        # newest artifact has verification_passed=True
        self.assertTrue(raw.get("verification_passed"))

    def test_markdown_contains_report_header(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            td = Path(tmpdir)
            _write_healing_artifact(td, "healing_decision_report.json")
            with patch("src.services.workbench_service._ARTIFACTS_DIR", td):
                from src.services.workbench_service import load_most_recent_artifact

                md, _ = load_most_recent_artifact()
        self.assertIn("#", md)  # has a markdown heading


if __name__ == "__main__":
    unittest.main()
