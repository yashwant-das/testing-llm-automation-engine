"""
Unit tests for the src/healing/ package.

Each module is tested in isolation:
  TestRunTest           — runner.run_test()           (mocked subprocess)
  TestExtractUrl        — evidence.extract_url_from_code()
  TestGatherEvidence    — evidence.gather_evidence()  (mocked collect_context)
  TestClassifier        — classifier.classify_failure_heuristic()  (smoke)
  TestAnalyzeAndPlan    — planner.analyze_and_plan()  (mocked LLMRouter)
  TestVerifyRepair      — verifier.verify_repair()    (mocked run_test)
  TestEmitArtifacts     — artifact_store.emit_artifacts() (temp directory)
  TestHealingInit       — src.healing __init__ re-exports
"""

import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from schemas.healing import (
    Evidence,
    ExecutionTimeline,
    HealingAction,
    HealingDecision,
)
from schemas.shared import FailureType, RunResult
from src.healing.artifact_store import emit_artifacts
from src.healing.classifier import classify_failure_heuristic
from src.healing.evidence import extract_url_from_code, gather_evidence
from src.healing.planner import analyze_and_plan
from src.healing.repair import apply_fix
from src.healing.runner import run_test
from src.healing.verifier import verify_repair

# ── Helpers ──────────────────────────────────────────────────────────────────


def _make_decision(
    *,
    original_code: str = "",
    fixed_code: str = "",
    description: str = "",
    failure_type: FailureType = FailureType.UNKNOWN,
) -> HealingDecision:
    return HealingDecision(
        test_file="dummy.spec.ts",
        failure_type=failure_type,
        failure_summary="test summary",
        evidence=Evidence(error_log="some error"),
        hypothesis="some hypothesis",
        confidence_score=0.9,
        reasoning_steps=["step 1"],
        action_taken=HealingAction(
            original_code=original_code,
            fixed_code=fixed_code,
            description=description,
        ),
    )


# ── runner.run_test ───────────────────────────────────────────────────────────


class TestRunTest(unittest.TestCase):
    @patch("subprocess.run")
    def test_passing_test_returns_passed_result(self, mock_run):
        mock_run.return_value = MagicMock(returncode=0, stdout="1 passed", stderr="")
        result = run_test("test.spec.ts")
        self.assertTrue(result.passed)
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout, "1 passed")

    @patch("subprocess.run")
    def test_failing_test_returns_failed_result(self, mock_run):
        mock_run.return_value = MagicMock(
            returncode=1, stdout="", stderr="Error: locator not found"
        )
        result = run_test("test.spec.ts")
        self.assertFalse(result.passed)
        self.assertEqual(result.returncode, 1)
        self.assertIn("locator not found", result.stderr)

    @patch(
        "subprocess.run",
        side_effect=subprocess.TimeoutExpired("npx", 60),
    )
    def test_timeout_returns_from_timeout(self, mock_run):
        result = run_test("test.spec.ts")
        self.assertFalse(result.passed)
        self.assertIn("timed out", result.output.lower())

    @patch("subprocess.run", side_effect=FileNotFoundError())
    def test_playwright_not_found(self, mock_run):
        result = run_test("test.spec.ts")
        self.assertFalse(result.passed)
        self.assertIn("Playwright not found", result.output)

    @patch("subprocess.run")
    def test_correct_command_constructed(self, mock_run):
        mock_run.return_value = MagicMock(returncode=0, stdout="ok", stderr="")
        run_test("my_test.spec.ts")
        args, kwargs = mock_run.call_args
        cmd = args[0]
        self.assertEqual(cmd[0], "npx")
        self.assertEqual(cmd[1], "playwright")
        self.assertEqual(cmd[2], "test")
        self.assertEqual(cmd[3], "my_test.spec.ts")

    @patch("subprocess.run")
    def test_none_stdout_coerced_to_empty(self, mock_run):
        mock_run.return_value = MagicMock(returncode=1, stdout=None, stderr=None)
        result = run_test("test.spec.ts")
        self.assertEqual(result.stdout, "")
        self.assertEqual(result.stderr, "")


# ── evidence.extract_url_from_code ───────────────────────────────────────────


class TestExtractUrl(unittest.TestCase):
    def test_single_quotes(self):
        code = "await page.goto('https://example.com/foo');"
        self.assertEqual(extract_url_from_code(code), "https://example.com/foo")

    def test_double_quotes(self):
        code = 'await page.goto("https://example.com/bar");'
        self.assertEqual(extract_url_from_code(code), "https://example.com/bar")

    def test_backtick(self):
        code = "await page.goto(`https://example.com/baz`);"
        self.assertEqual(extract_url_from_code(code), "https://example.com/baz")

    def test_no_goto_returns_none(self):
        code = "await page.click('#btn');"
        self.assertIsNone(extract_url_from_code(code))

    def test_empty_string_returns_none(self):
        self.assertIsNone(extract_url_from_code(""))

    def test_none_returns_none(self):
        self.assertIsNone(extract_url_from_code(None))

    def test_url_with_path_and_query(self):
        # The regex captures the full URL as written in the goto call,
        # including query strings — no stripping is applied.
        code = "await page.goto('https://app.example.com/login?ref=test');"
        url = extract_url_from_code(code)
        self.assertEqual(url, "https://app.example.com/login?ref=test")

    def test_multiline_code_finds_url(self):
        code = """
import { test } from '@playwright/test';

test('login', async ({ page }) => {
    await page.goto('https://example.com/login');
    await page.click('#submit');
});
"""
        self.assertEqual(extract_url_from_code(code), "https://example.com/login")


# ── evidence.gather_evidence ─────────────────────────────────────────────────


class TestGatherEvidence(unittest.TestCase):
    """gather_evidence() tests — collect_context is mocked to avoid real browser."""

    def _no_op_collect(self, url, **kwargs):
        """Return an empty ContextSnapshot so no browser is launched."""
        from schemas.artifacts import ContextSnapshot

        return ContextSnapshot(url=url)

    def test_stderr_preferred_over_stdout(self):
        result = RunResult(
            returncode=1, stdout="stdout content", stderr="stderr content"
        )
        with patch(
            "src.healing.evidence.collect_context", side_effect=self._no_op_collect
        ):
            with patch.object(Path, "exists", return_value=False):
                evidence = gather_evidence("non_existent.spec.ts", result)
        self.assertEqual(evidence.error_log, "stderr content")

    def test_stdout_used_when_no_stderr(self):
        result = RunResult(returncode=1, stdout="stdout content", stderr="")
        with patch(
            "src.healing.evidence.collect_context", side_effect=self._no_op_collect
        ):
            with patch.object(Path, "exists", return_value=False):
                evidence = gather_evidence("non_existent.spec.ts", result)
        self.assertEqual(evidence.error_log, "stdout content")

    def test_no_screenshot_when_results_dir_missing(self):
        result = RunResult(returncode=1, stdout="err", stderr="")
        with patch(
            "src.healing.evidence.collect_context", side_effect=self._no_op_collect
        ):
            with patch.object(Path, "exists", return_value=False):
                evidence = gather_evidence("non_existent.spec.ts", result)
        self.assertIsNone(evidence.screenshot_path)

    def test_dom_snippet_populated_from_live_page(self):
        """collect_context() result propagates to evidence.dom_snippet."""
        from schemas.artifacts import ContextSnapshot

        def mock_collect(url, **kwargs):
            return ContextSnapshot(url=url, html="<html>live</html>")

        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".spec.ts", delete=False
        ) as tmp:
            tmp.write("await page.goto('https://example.com');")
            tmp_path = tmp.name

        result = RunResult(returncode=1, stdout="err", stderr="")
        with patch("src.healing.evidence.collect_context", side_effect=mock_collect):
            evidence = gather_evidence(tmp_path, result)

        self.assertIsNotNone(evidence.dom_snippet)
        self.assertEqual(evidence.dom_snippet, "<html>live</html>")

        import os

        os.unlink(tmp_path)

    def test_dom_snippet_empty_when_context_fails(self):
        """When collect_context returns empty snapshot, dom_snippet is None."""
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".spec.ts", delete=False
        ) as tmp:
            tmp.write("await page.goto('https://example.com');")
            tmp_path = tmp.name

        result = RunResult(returncode=1, stdout="err", stderr="")
        with patch(
            "src.healing.evidence.collect_context",
            side_effect=self._no_op_collect,
        ):
            evidence = gather_evidence(tmp_path, result)

        # Empty snapshot → dom_snippet is None
        self.assertIsNone(evidence.dom_snippet)

        import os

        os.unlink(tmp_path)


# ── classifier.classify_failure_heuristic (smoke) ────────────────────────────
# Full coverage lives in unit_test_classification.py; this ensures the module
# is importable independently from src.healing.classifier.


class TestClassifierSmoke(unittest.TestCase):
    def test_timeout_pattern(self):
        f_type, conf, _ = classify_failure_heuristic("TimeoutError: 30000ms exceeded")
        self.assertEqual(f_type, FailureType.TIMEOUT)
        self.assertEqual(conf, 1.0)

    def test_empty_logs_return_unknown(self):
        f_type, conf, _ = classify_failure_heuristic("")
        self.assertEqual(f_type, FailureType.UNKNOWN)
        self.assertEqual(conf, 0.0)

    def test_no_match_returns_unknown(self):
        f_type, conf, _ = classify_failure_heuristic("some random log output")
        self.assertEqual(f_type, FailureType.UNKNOWN)


# ── planner.analyze_and_plan ─────────────────────────────────────────────────


def _make_analysis_json(
    failure_type: str = "TIMEOUT",
    hypothesis: str = "selector moved",
    original_code: str = "await page.click('#old')",
    fixed_code: str = "await page.click('#new')",
) -> str:
    return json.dumps(
        {
            "failure_type": failure_type,
            "failure_summary": "Test timed out waiting for element",
            "hypothesis": hypothesis,
            "confidence_score": 0.9,
            "reasoning_steps": ["Timeout detected", "Selector may have moved"],
            "action_taken": {
                "original_code": original_code,
                "fixed_code": fixed_code,
                "description": "Updated selector",
            },
        }
    )


class TestAnalyzeAndPlan(unittest.TestCase):
    def _mock_router(self, response_json: str) -> MagicMock:
        mock_router = MagicMock()
        mock_router.complete_primary.return_value = MagicMock(
            content=f"```json\n{response_json}\n```",
            model_used="mock-model",  # Phase 9: planner passes this to HealingDecision
        )
        return mock_router

    @patch("src.healing.planner.get_default_router")
    @patch(
        "src.healing.planner.load_prompt",
        return_value="Heal {failure_type} {confidence} {reason}",
    )
    def test_returns_healing_decision_on_valid_response(
        self, _mock_prompt, mock_get_router
    ):
        mock_get_router.return_value = self._mock_router(_make_analysis_json())
        evidence = Evidence(error_log="TimeoutError: timed out waiting for selector")
        decision = analyze_and_plan(
            "test.spec.ts", "await page.click('#old')", evidence
        )
        self.assertIsInstance(decision, HealingDecision)
        self.assertEqual(decision.failure_type, FailureType.TIMEOUT)
        self.assertEqual(decision.hypothesis, "selector moved")

    @patch("src.healing.planner.get_default_router")
    @patch(
        "src.healing.planner.load_prompt",
        return_value="Heal {failure_type} {confidence} {reason}",
    )
    def test_heuristic_overrides_llm_unknown(self, _mock_prompt, mock_get_router):
        # LLM returns UNKNOWN but heuristic is high-confidence TIMEOUT
        analysis = _make_analysis_json(failure_type="UNKNOWN")
        mock_get_router.return_value = self._mock_router(analysis)
        # High-confidence timeout log — heuristic will fire at conf=1.0
        evidence = Evidence(error_log="TimeoutError: Timeout 30000ms exceeded")
        decision = analyze_and_plan("test.spec.ts", "code", evidence)
        # Heuristic override must apply
        self.assertEqual(decision.failure_type, FailureType.TIMEOUT)

    @patch("src.healing.planner.get_default_router")
    @patch(
        "src.healing.planner.load_prompt",
        return_value="Heal {failure_type} {confidence} {reason}",
    )
    def test_fallback_decision_on_llm_error(self, _mock_prompt, mock_get_router):
        mock_get_router.return_value.complete_primary.side_effect = RuntimeError(
            "connection refused"
        )
        evidence = Evidence(error_log="some error")
        decision = analyze_and_plan("test.spec.ts", "code", evidence)
        self.assertEqual(decision.confidence_score, 0.0)
        self.assertIn("failed to analyze", decision.failure_summary)
        self.assertEqual(decision.failure_type, FailureType.UNKNOWN)

    @patch("src.healing.planner.get_default_router")
    @patch(
        "src.healing.planner.load_prompt",
        return_value="Heal {failure_type} {confidence} {reason}",
    )
    def test_llm_called_with_code_and_logs(self, _mock_prompt, mock_get_router):
        mock_router = self._mock_router(_make_analysis_json())
        mock_get_router.return_value = mock_router
        evidence = Evidence(error_log="error here", dom_snippet=None)
        analyze_and_plan("test.spec.ts", "my test code", evidence)
        call_kwargs = mock_router.complete_primary.call_args[1]
        user_msg = call_kwargs["messages"][1]["content"]
        self.assertIn("my test code", user_msg)
        self.assertIn("error here", user_msg)

    @patch("src.healing.planner.get_default_router")
    @patch(
        "src.healing.planner.load_prompt",
        return_value="Heal {failure_type} {confidence} {reason}",
    )
    def test_dom_snippet_included_when_present(self, _mock_prompt, mock_get_router):
        mock_router = self._mock_router(_make_analysis_json())
        mock_get_router.return_value = mock_router
        evidence = Evidence(error_log="error", dom_snippet="<div>page</div>")
        analyze_and_plan("test.spec.ts", "code", evidence)
        call_kwargs = mock_router.complete_primary.call_args[1]
        user_msg = call_kwargs["messages"][1]["content"]
        self.assertIn("<div>page</div>", user_msg)


# ── repair.apply_fix (smoke) ──────────────────────────────────────────────────
# Full coverage lives in unit_test_fixer.py; this ensures the module is
# importable independently from src.healing.repair.


class TestRepairSmoke(unittest.TestCase):
    def test_exact_match_replaced(self):
        current = "await page.click('#old');"
        decision = _make_decision(
            original_code="await page.click('#old');",
            fixed_code="await page.click('#new');",
        )
        result = apply_fix("test.spec.ts", current, decision)
        self.assertIn("#new", result)
        self.assertNotIn("#old", result)

    def test_no_match_returns_original(self):
        current = "await page.click('#different');"
        decision = _make_decision(
            original_code="await page.click('#nonexistent');",
            fixed_code="await page.click('#new');",
        )
        result = apply_fix("test.spec.ts", current, decision)
        self.assertEqual(result, current)

    def test_empty_target_returns_original(self):
        current = "some code"
        decision = _make_decision(original_code="", fixed_code="replacement")
        result = apply_fix("test.spec.ts", current, decision)
        self.assertEqual(result, current)


# ── verifier.verify_repair ────────────────────────────────────────────────────


class TestVerifyRepair(unittest.TestCase):
    @patch("src.healing.verifier.run_test")
    def test_sets_verification_passed_on_success(self, mock_run_test):
        mock_run_test.return_value = RunResult(
            returncode=0, stdout="1 passed", stderr=""
        )
        decision = _make_decision()
        result = verify_repair("test.spec.ts", decision)
        self.assertTrue(decision.verification_passed)
        self.assertTrue(result.passed)

    @patch("src.healing.verifier.run_test")
    def test_sets_verification_failed_on_failure(self, mock_run_test):
        mock_run_test.return_value = RunResult(returncode=1, stdout="", stderr="Error")
        decision = _make_decision()
        result = verify_repair("test.spec.ts", decision)
        self.assertFalse(decision.verification_passed)
        self.assertFalse(result.passed)

    @patch("src.healing.verifier.run_test")
    def test_verification_log_set(self, mock_run_test):
        mock_run_test.return_value = RunResult(
            returncode=1, stdout="stdout log", stderr=""
        )
        decision = _make_decision()
        verify_repair("test.spec.ts", decision)
        # output is the combined log property from RunResult
        self.assertIsNotNone(decision.verification_log)

    @patch("src.healing.verifier.run_test")
    def test_returns_run_result_for_next_loop_iteration(self, mock_run_test):
        expected_result = RunResult(returncode=0, stdout="ok", stderr="")
        mock_run_test.return_value = expected_result
        decision = _make_decision()
        returned = verify_repair("test.spec.ts", decision)
        self.assertIs(returned, expected_result)


# ── artifact_store.emit_artifacts ─────────────────────────────────────────────


class TestEmitArtifacts(unittest.TestCase):
    def _make_decision_for_artifacts(self) -> HealingDecision:
        return _make_decision(
            original_code="old code",
            fixed_code="new code",
            description="Updated selector",
            failure_type=FailureType.LOCATOR_DRIFT,
        )

    def test_writes_two_json_files(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            artifacts_dir = Path(tmpdir)
            decision = self._make_decision_for_artifacts()
            timeline = ExecutionTimeline()
            timeline.add_step("Start", "Session started")
            timeline.add_step("End", "Session ended")

            with patch("src.healing.artifact_store.ARTIFACTS_DIR", artifacts_dir):
                emit_artifacts(decision, timeline)

            json_files = sorted(artifacts_dir.glob("*.json"))
            self.assertEqual(len(json_files), 2)

    def test_decision_file_is_valid_json(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            artifacts_dir = Path(tmpdir)
            decision = self._make_decision_for_artifacts()
            timeline = ExecutionTimeline()
            timeline.add_step("Start", "Session started")

            with patch("src.healing.artifact_store.ARTIFACTS_DIR", artifacts_dir):
                emit_artifacts(decision, timeline)

            decision_files = list(artifacts_dir.glob("healing_decision_*.json"))
            self.assertEqual(len(decision_files), 1)
            content = decision_files[0].read_text(encoding="utf-8")
            parsed = json.loads(content)
            self.assertIn("failure_type", parsed)

    def test_timeline_file_is_valid_json(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            artifacts_dir = Path(tmpdir)
            decision = self._make_decision_for_artifacts()
            timeline = ExecutionTimeline()
            timeline.add_step("Start", "Session started")

            with patch("src.healing.artifact_store.ARTIFACTS_DIR", artifacts_dir):
                emit_artifacts(decision, timeline)

            timeline_files = list(artifacts_dir.glob("execution_timeline_*.json"))
            self.assertEqual(len(timeline_files), 1)
            content = timeline_files[0].read_text(encoding="utf-8")
            parsed = json.loads(content)
            self.assertIn("steps", parsed)

    def test_file_names_contain_timestamp(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            artifacts_dir = Path(tmpdir)
            decision = self._make_decision_for_artifacts()
            timeline = ExecutionTimeline()
            timeline.add_step("Start", "Session started")

            with patch("src.healing.artifact_store.ARTIFACTS_DIR", artifacts_dir):
                emit_artifacts(decision, timeline)

            files = sorted(artifacts_dir.glob("*.json"))
            for f in files:
                # Name must be: prefix_YYYYMMDD_HHMMSS.json
                parts = f.stem.split("_")
                # Last two segments are date and time
                self.assertEqual(len(parts[-1]), 6)  # HHMMSS
                self.assertEqual(len(parts[-2]), 8)  # YYYYMMDD


# ── src.healing __init__ re-exports ──────────────────────────────────────────


class TestHealingInit(unittest.TestCase):
    def test_all_public_symbols_importable(self):
        from src.healing import (  # noqa: F401
            analyze_and_plan,
            apply_fix,
            attempt_healing,
            classify_failure_heuristic,
            emit_artifacts,
            extract_url_from_code,
            gather_evidence,
            run_test,
            verify_repair,
        )

    def test_attempt_healing_callable(self):
        from src.healing import attempt_healing

        self.assertTrue(callable(attempt_healing))

    def test_modules_independently_importable(self):
        """Each sub-module can be imported without touching the others."""
        import importlib

        modules = [
            "src.healing.runner",
            "src.healing.evidence",
            "src.healing.classifier",
            "src.healing.planner",
            "src.healing.repair",
            "src.healing.verifier",
            "src.healing.artifact_store",
        ]
        for mod in modules:
            with self.subTest(module=mod):
                loaded = importlib.import_module(mod)
                self.assertIsNotNone(loaded)


# ── RepairStrategy labels ─────────────────────────────────────────────────────


class TestRepairStrategyLabels(unittest.TestCase):
    def test_all_strategies_have_a_label(self):
        from schemas.healing import REPAIR_STRATEGY_LABELS, RepairStrategy

        for strategy in RepairStrategy:
            with self.subTest(strategy=strategy):
                self.assertIn(strategy, REPAIR_STRATEGY_LABELS)
                self.assertIsInstance(REPAIR_STRATEGY_LABELS[strategy], str)
                self.assertTrue(REPAIR_STRATEGY_LABELS[strategy])

    def test_label_count_matches_enum_count(self):
        from schemas.healing import REPAIR_STRATEGY_LABELS, RepairStrategy

        self.assertEqual(len(REPAIR_STRATEGY_LABELS), len(RepairStrategy))


# ── attempt_healing tracer session ────────────────────────────────────────────


class TestAttemptHealingTracerSession(unittest.TestCase):
    """Verifies that attempt_healing starts and ends a tracer session regardless
    of outcome so CLI runs produce the same span structure as UI runs."""

    def _make_mock_tracer(self):
        tracer = MagicMock()
        tracer.start_session.return_value = "trace-test-id"
        return tracer

    @patch("src.observability.get_tracer")
    @patch("src.healing.run_test")
    @patch("src.healing.gather_evidence")
    @patch("src.healing.emit_artifacts")
    def test_session_started_and_ended_on_initial_pass(
        self, mock_emit, mock_evidence, mock_run_test, mock_get_tracer
    ):
        mock_tracer = self._make_mock_tracer()
        mock_get_tracer.return_value = mock_tracer
        mock_run_test.return_value = MagicMock(passed=True, returncode=0)
        mock_evidence.return_value = Evidence(error_log="")

        # Use tests/generated/ — the only allowed directory for validate_file_path.
        test_path = Path("tests/generated/_tracer_test.spec.ts")
        test_path.write_text("// tracer test fixture", encoding="utf-8")
        try:
            from src.healing import attempt_healing

            attempt_healing(str(test_path), max_retries=1)
        finally:
            test_path.unlink(missing_ok=True)

        mock_tracer.start_session.assert_called_once_with("healing")
        mock_tracer.end_session.assert_called_once()
        _, kwargs = mock_tracer.end_session.call_args
        self.assertTrue(kwargs.get("success", False))

    @patch("src.observability.get_tracer")
    def test_session_ended_even_when_file_missing(self, mock_get_tracer):
        mock_tracer = self._make_mock_tracer()
        mock_get_tracer.return_value = mock_tracer

        from src.healing import attempt_healing

        # Path in allowed directory but not on disk — triggers "File not found" branch.
        result = attempt_healing("tests/generated/_missing_test.spec.ts", max_retries=1)

        mock_tracer.start_session.assert_called_once_with("healing")
        mock_tracer.end_session.assert_called_once()
        self.assertIn("Error", result)


if __name__ == "__main__":
    unittest.main()
