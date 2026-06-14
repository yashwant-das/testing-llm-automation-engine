"""
Stage 4 — Evaluation workspace unit tests.

Covers:
  run_classification_benchmark() — saves report to benchmarks/reports/
  load_benchmark_history()        — delta table from saved reports
  check_llm_available()           — returns False when router raises
  run_generation_benchmark_ui()   — returns LLM-unavailable message when guard fails
"""

import json
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from schemas.evaluation import BenchmarkRun, BenchmarkRunConfig, EvaluationResult

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

PROJECT_ROOT = Path(__file__).resolve().parent.parent
_DATASET_PATH = (
    PROJECT_ROOT / "benchmarks" / "healing" / "fixtures" / "repair_scenarios.json"
)


def _make_run(
    benchmark_type: str = "healing-classification",
    model: str = "heuristic-classifier",
    pass_fraction: float = 1.0,
    mean_score: float = 1.0,
) -> BenchmarkRun:
    """Build a minimal BenchmarkRun for testing."""
    n_cases = 4
    n_pass = round(pass_fraction * n_cases)
    results = [
        EvaluationResult(
            example_id=f"case-{i}",
            passed=(i < n_pass),
            score=mean_score,
            duration_ms=5,
            details={},
        )
        for i in range(n_cases)
    ]
    config = BenchmarkRunConfig(
        model=model,
        provider="local",
        prompt_name="test-prompt",
        prompt_version="1",
        prompt_hash="abc123",
        temperature=0.0,
        dataset_version="1.0.0",
        benchmark_type=benchmark_type,
    )
    return BenchmarkRun(config=config, results=results)


# ---------------------------------------------------------------------------
# run_classification_benchmark() — persists report
# ---------------------------------------------------------------------------


class TestRunClassificationBenchmarkPersistence(unittest.TestCase):
    """run_classification_benchmark() saves a report to benchmarks/reports/."""

    def test_report_saved_to_reports_dir(self):
        """After a successful run, a JSON report is written to _REPORTS_DIR."""
        if not _DATASET_PATH.exists():
            self.skipTest("Healing dataset not present")

        with tempfile.TemporaryDirectory() as tmpdir:
            reports_dir = Path(tmpdir)
            with patch("src.services.workbench_service._REPORTS_DIR", reports_dir):
                from src.services.workbench_service import run_classification_benchmark

                run_classification_benchmark()

            saved = list(reports_dir.glob("*.json"))
            self.assertEqual(len(saved), 1, f"Expected 1 report, got {saved}")
            raw = json.loads(saved[0].read_text())
            self.assertIn("config", raw)
            self.assertIn("results", raw)

    def test_save_failure_doesnt_crash_function(self):
        """If save_report raises, the benchmark result markdown is still returned."""
        if not _DATASET_PATH.exists():
            self.skipTest("Healing dataset not present")

        with patch(
            "schemas.evaluation.BenchmarkRun.save_report",
            side_effect=OSError("disk full"),
        ):
            from src.services.workbench_service import run_classification_benchmark

            result = run_classification_benchmark()

        self.assertIsInstance(result, str)
        self.assertIn("Heuristic Classification Benchmark", result)

    def test_result_mentions_report_file(self):
        """The returned markdown mentions the saved report filename."""
        if not _DATASET_PATH.exists():
            self.skipTest("Healing dataset not present")

        with tempfile.TemporaryDirectory() as tmpdir:
            reports_dir = Path(tmpdir)
            with patch("src.services.workbench_service._REPORTS_DIR", reports_dir):
                from src.services.workbench_service import run_classification_benchmark

                result = run_classification_benchmark()

        # The report note should appear in the footer line
        self.assertIn("healing-classification", result)

    def test_result_mentions_not_recorded_when_save_fails(self):
        """When save fails the footer shows *(report could not be saved)*."""
        if not _DATASET_PATH.exists():
            self.skipTest("Healing dataset not present")

        with patch(
            "schemas.evaluation.BenchmarkRun.save_report",
            side_effect=OSError("no space"),
        ):
            from src.services.workbench_service import run_classification_benchmark

            result = run_classification_benchmark()

        self.assertIn("*(report could not be saved)*", result)


# ---------------------------------------------------------------------------
# load_benchmark_history()
# ---------------------------------------------------------------------------


class TestLoadBenchmarkHistory(unittest.TestCase):
    """load_benchmark_history() returns a markdown delta table."""

    def _write_run(self, reports_dir: Path, run: BenchmarkRun, name: str) -> None:
        path = reports_dir / name
        path.write_text(run.to_json(), encoding="utf-8")

    def test_no_reports_dir_returns_placeholder(self):
        absent = Path("/tmp/_nonexistent_reports_stage4_test_xyz")
        with patch("src.services.workbench_service._REPORTS_DIR", absent):
            from src.services.workbench_service import load_benchmark_history

            md = load_benchmark_history()
        self.assertIn("No reports saved yet", md)

    def test_empty_reports_dir_returns_placeholder(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch("src.services.workbench_service._REPORTS_DIR", Path(tmpdir)):
                from src.services.workbench_service import load_benchmark_history

                md = load_benchmark_history()
        self.assertIn("No reports found", md)

    def test_single_run_shows_baseline(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            td = Path(tmpdir)
            self._write_run(td, _make_run(pass_fraction=1.0), "run1.json")
            with patch("src.services.workbench_service._REPORTS_DIR", td):
                from src.services.workbench_service import load_benchmark_history

                md = load_benchmark_history()
        self.assertIn("## Benchmark History", md)
        self.assertIn("*(baseline)*", md)

    def test_two_runs_show_delta_column(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            td = Path(tmpdir)
            old_path = td / "run_old.json"
            new_path = td / "run_new.json"
            old_path.write_text(
                _make_run(pass_fraction=0.75).to_json(), encoding="utf-8"
            )
            time.sleep(0.02)  # ensure different mtimes
            new_path.write_text(
                _make_run(pass_fraction=1.0).to_json(), encoding="utf-8"
            )
            with patch("src.services.workbench_service._REPORTS_DIR", td):
                from src.services.workbench_service import load_benchmark_history

                md = load_benchmark_history()
        self.assertIn("## Benchmark History", md)
        self.assertIn("+", md)  # positive delta

    def test_table_headers_present(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            td = Path(tmpdir)
            self._write_run(td, _make_run(), "run1.json")
            with patch("src.services.workbench_service._REPORTS_DIR", td):
                from src.services.workbench_service import load_benchmark_history

                md = load_benchmark_history()
        self.assertIn("| Run | Pass rate |", md)
        self.assertIn("| --- |", md)

    def test_corrupted_report_skipped_gracefully(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            td = Path(tmpdir)
            (td / "corrupted.json").write_text("not-json", encoding="utf-8")
            self._write_run(td, _make_run(), "good_run.json")
            with patch("src.services.workbench_service._REPORTS_DIR", td):
                from src.services.workbench_service import load_benchmark_history

                md = load_benchmark_history()
        self.assertIn("## Benchmark History", md)
        self.assertIn("heuristic-classifier", md)

    def test_model_name_appears_in_table(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            td = Path(tmpdir)
            self._write_run(td, _make_run(model="my-test-model"), "run_with_model.json")
            with patch("src.services.workbench_service._REPORTS_DIR", td):
                from src.services.workbench_service import load_benchmark_history

                md = load_benchmark_history()
        self.assertIn("my-test-model", md)


# ---------------------------------------------------------------------------
# check_llm_available()
# ---------------------------------------------------------------------------


class TestCheckLlmAvailable(unittest.TestCase):
    """check_llm_available() probes the LLM and returns (bool, str)."""

    def test_returns_false_when_router_raises(self):
        mock_router = MagicMock()
        mock_router.complete_primary.side_effect = ConnectionRefusedError(
            "connection refused"
        )
        with patch("src.llm.get_default_router", return_value=mock_router):
            from src.services.workbench_service import check_llm_available

            available, msg = check_llm_available()

        self.assertFalse(available)
        self.assertIn("not reachable", msg)

    def test_returns_true_when_router_succeeds(self):
        mock_router = MagicMock()
        mock_router.complete_primary.return_value = MagicMock(content="ok")
        with patch("src.llm.get_default_router", return_value=mock_router):
            from src.services.workbench_service import check_llm_available

            available, msg = check_llm_available()

        self.assertTrue(available)
        self.assertIn("reachable", msg)

    def test_returns_false_on_timeout(self):
        mock_router = MagicMock()
        mock_router.complete_primary.side_effect = TimeoutError("timed out")
        with patch("src.llm.get_default_router", return_value=mock_router):
            from src.services.workbench_service import check_llm_available

            available, msg = check_llm_available()

        self.assertFalse(available)
        self.assertIn("timed out", msg.lower())

    def test_returns_tuple(self):
        mock_router = MagicMock()
        mock_router.complete_primary.return_value = MagicMock(content="ok")
        with patch("src.llm.get_default_router", return_value=mock_router):
            from src.services.workbench_service import check_llm_available

            result = check_llm_available()

        self.assertIsInstance(result, tuple)
        self.assertEqual(len(result), 2)
        self.assertIsInstance(result[0], bool)
        self.assertIsInstance(result[1], str)


# ---------------------------------------------------------------------------
# run_generation_benchmark_ui() — LLM guard
# ---------------------------------------------------------------------------


class TestRunGenerationBenchmarkUi(unittest.TestCase):
    """run_generation_benchmark_ui() gates on LLM availability."""

    def test_llm_unavailable_returns_clear_error_message(self):
        with patch(
            "src.services.workbench_service.check_llm_available",
            return_value=(False, "LLM not reachable: connection refused"),
        ):
            from src.services.workbench_service import run_generation_benchmark_ui

            result = run_generation_benchmark_ui()

        self.assertIn("LLM Unavailable", result)
        self.assertIn("connection refused", result)

    def test_llm_unavailable_result_has_markdown_header(self):
        with patch(
            "src.services.workbench_service.check_llm_available",
            return_value=(False, "LLM not reachable: timeout"),
        ):
            from src.services.workbench_service import run_generation_benchmark_ui

            result = run_generation_benchmark_ui()

        self.assertIn("##", result)
        self.assertIn("❌", result)

    def test_llm_unavailable_mentions_remediation(self):
        with patch(
            "src.services.workbench_service.check_llm_available",
            return_value=(False, "LLM not reachable: refused"),
        ):
            from src.services.workbench_service import run_generation_benchmark_ui

            result = run_generation_benchmark_ui()

        # Should advise the user on what to do
        self.assertIn("LM Studio", result)
        self.assertIn("Ollama", result)

    def test_missing_dataset_returns_error_when_llm_available(self):
        absent = Path("/tmp/_nonexistent_gen_dataset_stage4_xyz.json")
        with (
            patch(
                "src.services.workbench_service.check_llm_available",
                return_value=(True, "LLM reachable"),
            ),
            patch("src.services.workbench_service._GEN_DATASET_PATH", absent),
        ):
            from src.services.workbench_service import run_generation_benchmark_ui

            result = run_generation_benchmark_ui()

        self.assertIn("not found", result.lower())


if __name__ == "__main__":
    unittest.main()
