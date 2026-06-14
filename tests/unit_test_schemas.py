"""
Unit tests for all Pydantic schemas.

Covers: field validation, coercion, Pydantic parsing, serialization,
and the parse_llm_response() integration point.
"""

import json
import unittest

from pydantic import ValidationError

from schemas.generation import GenerationResult
from schemas.healing import (
    Evidence,
    ExecutionTimeline,
    HealingAction,
    HealingAnalysis,
    HealingDecision,
)
from schemas.shared import FailureType, RunResult
from src.utils.llm import parse_llm_response

# ---------------------------------------------------------------------------
# RunResult
# ---------------------------------------------------------------------------


class TestRunResult(unittest.TestCase):
    def test_passed_property(self):
        r = RunResult(returncode=0, stdout="ok", stderr="")
        self.assertTrue(r.passed)

    def test_failed_property(self):
        r = RunResult(returncode=1, stdout="", stderr="err")
        self.assertFalse(r.passed)

    def test_output_prefers_stdout(self):
        r = RunResult(returncode=0, stdout="out", stderr="err")
        self.assertEqual(r.output, "out")

    def test_output_falls_back_to_stderr(self):
        r = RunResult(returncode=1, stdout="", stderr="fail")
        self.assertEqual(r.output, "fail")

    def test_from_timeout(self):
        r = RunResult.from_timeout()
        self.assertEqual(r.returncode, 1)
        self.assertIn("timed out", r.stderr)

    def test_from_error(self):
        r = RunResult.from_error("playwright not found")
        self.assertEqual(r.returncode, 1)
        self.assertEqual(r.stderr, "playwright not found")


# ---------------------------------------------------------------------------
# HealingAction — list coercion validator
# ---------------------------------------------------------------------------


class TestHealingAction(unittest.TestCase):
    def test_string_fields_accepted(self):
        a = HealingAction(original_code="old", fixed_code="new", description="desc")
        self.assertEqual(a.original_code, "old")

    def test_list_original_code_coerced_to_string(self):
        """LLMs sometimes return code as a list of lines."""
        a = HealingAction(
            original_code=["line1", "line2"],
            fixed_code="new",
            description="desc",
        )
        self.assertEqual(a.original_code, "line1\nline2")

    def test_list_fixed_code_coerced_to_string(self):
        a = HealingAction(
            original_code="old",
            fixed_code=["line1", "line2"],
            description="desc",
        )
        self.assertEqual(a.fixed_code, "line1\nline2")


# ---------------------------------------------------------------------------
# HealingAnalysis — structured LLM response schema
# ---------------------------------------------------------------------------


class TestHealingAnalysis(unittest.TestCase):
    def _valid_payload(self) -> dict:
        return {
            "failure_type": "TIMEOUT",
            "failure_summary": "Selector timed out",
            "hypothesis": "The selector changed",
            "confidence_score": 0.95,
            "reasoning_steps": ["step 1", "step 2"],
            "action_taken": {
                "original_code": "old",
                "fixed_code": "new",
                "description": "changed selector",
            },
        }

    def test_valid_payload_parses(self):
        a = HealingAnalysis(**self._valid_payload())
        self.assertEqual(a.failure_type, FailureType.TIMEOUT)
        self.assertAlmostEqual(a.confidence_score, 0.95)

    def test_confidence_clamped_above_1(self):
        payload = self._valid_payload()
        payload["confidence_score"] = 1.05
        a = HealingAnalysis(**payload)
        self.assertAlmostEqual(a.confidence_score, 1.0)

    def test_confidence_clamped_below_0(self):
        payload = self._valid_payload()
        payload["confidence_score"] = -0.1
        a = HealingAnalysis(**payload)
        self.assertAlmostEqual(a.confidence_score, 0.0)

    def test_single_string_step_coerced_to_list(self):
        payload = self._valid_payload()
        payload["reasoning_steps"] = "just one step"
        a = HealingAnalysis(**payload)
        self.assertEqual(a.reasoning_steps, ["just one step"])

    def test_failure_type_string_coercion(self):
        payload = self._valid_payload()
        payload["failure_type"] = "LOCATOR_DRIFT"
        a = HealingAnalysis(**payload)
        self.assertEqual(a.failure_type, FailureType.LOCATOR_DRIFT)

    def test_invalid_failure_type_raises(self):
        payload = self._valid_payload()
        payload["failure_type"] = "INVALID_TYPE_XYZ"
        with self.assertRaises(ValidationError):
            HealingAnalysis(**payload)

    def test_missing_required_field_raises(self):
        payload = self._valid_payload()
        del payload["hypothesis"]
        with self.assertRaises(ValidationError):
            HealingAnalysis(**payload)


# ---------------------------------------------------------------------------
# HealingDecision — full artifact schema
# ---------------------------------------------------------------------------


class TestHealingDecision(unittest.TestCase):
    def _make_decision(self, **overrides) -> HealingDecision:
        defaults = dict(
            test_file="tests/generated/example.spec.ts",
            failure_type=FailureType.LOCATOR_DRIFT,
            failure_summary="Selector drifted",
            evidence=Evidence(error_log="locator resolved to 0 elements"),
            hypothesis="Selector attribute changed",
            confidence_score=0.9,
            reasoning_steps=["step 1"],
            action_taken=HealingAction(
                original_code="old", fixed_code="new", description="fix"
            ),
        )
        defaults.update(overrides)
        return HealingDecision(**defaults)

    def test_construction_succeeds(self):
        d = self._make_decision()
        self.assertFalse(d.verification_passed)
        self.assertIsNone(d.verification_log)

    def test_from_analysis(self):
        analysis = HealingAnalysis(
            failure_type=FailureType.TIMEOUT,
            failure_summary="timed out",
            hypothesis="slow element",
            confidence_score=0.8,
            reasoning_steps=["checked logs"],
            action_taken=HealingAction(
                original_code="old", fixed_code="new", description="fix"
            ),
        )
        evidence = Evidence(error_log="TimeoutError")
        d = HealingDecision.from_analysis(
            test_file="test.ts", analysis=analysis, evidence=evidence
        )
        self.assertEqual(d.failure_type, FailureType.TIMEOUT)
        self.assertEqual(d.hypothesis, "slow element")

    def test_to_dict_serializes_enum_as_string(self):
        d = self._make_decision()
        data = d.to_dict()
        self.assertEqual(data["failure_type"], "LOCATOR_DRIFT")

    def test_to_json_round_trips(self):
        d = self._make_decision()
        json_str = d.to_json()
        parsed = json.loads(json_str)
        self.assertEqual(parsed["failure_type"], "LOCATOR_DRIFT")
        self.assertEqual(parsed["hypothesis"], "Selector attribute changed")

    def test_to_markdown_contains_key_fields(self):
        d = self._make_decision(verification_passed=True)
        md = d.to_markdown()
        self.assertIn("LOCATOR_DRIFT", md)
        self.assertIn("Selector attribute changed", md)
        self.assertIn("Fixed", md)

    def test_confidence_score_out_of_range_raises(self):
        with self.assertRaises(ValidationError):
            self._make_decision(confidence_score=1.5)

    def test_string_failure_type_coerced(self):
        d = self._make_decision(failure_type="ASSERTION_FAILED")
        self.assertEqual(d.failure_type, FailureType.ASSERTION_FAILED)


# ---------------------------------------------------------------------------
# ExecutionTimeline
# ---------------------------------------------------------------------------


class TestExecutionTimeline(unittest.TestCase):
    def test_add_step(self):
        t = ExecutionTimeline()
        t.add_step("Start", "session started")
        self.assertEqual(len(t.steps), 1)
        self.assertEqual(t.steps[0].step, "Start")

    def test_to_json_round_trips(self):
        t = ExecutionTimeline()
        t.add_step("Step1", "details1")
        t.add_step("Step2", "details2")
        data = json.loads(t.to_json())
        self.assertEqual(len(data["steps"]), 2)
        self.assertEqual(data["steps"][0]["step"], "Step1")


# ---------------------------------------------------------------------------
# GenerationResult
# ---------------------------------------------------------------------------


class TestGenerationResult(unittest.TestCase):
    def test_valid_code_accepted(self):
        code = "import { test } from '@playwright/test';\ntest('foo', async () => {});"
        r = GenerationResult(code=code)
        self.assertEqual(r.code, code.strip())

    def test_empty_code_raises(self):
        with self.assertRaises(ValidationError):
            GenerationResult(code="")

    def test_whitespace_only_raises(self):
        with self.assertRaises(ValidationError):
            GenerationResult(code="   \n  ")

    def test_code_is_stripped(self):
        r = GenerationResult(code="  const x = 1;  ")
        self.assertEqual(r.code, "const x = 1;")

    def test_has_playwright_import_true(self):
        r = GenerationResult(code="import { test } from '@playwright/test';")
        self.assertTrue(r.has_playwright_import)

    def test_has_playwright_import_false(self):
        r = GenerationResult(code="const x = 1;")
        self.assertFalse(r.has_playwright_import)

    def test_has_test_block(self):
        r = GenerationResult(code="test('foo', async ({ page }) => {});")
        self.assertTrue(r.has_test_block)

    def test_line_count(self):
        r = GenerationResult(code="line1\nline2\nline3")
        self.assertEqual(r.line_count, 3)


# ---------------------------------------------------------------------------
# parse_llm_response — integration
# ---------------------------------------------------------------------------


class TestParseLlmResponse(unittest.TestCase):
    def _valid_json(self) -> str:
        return json.dumps(
            {
                "failure_type": "TIMEOUT",
                "failure_summary": "timed out",
                "hypothesis": "selector missing",
                "confidence_score": 0.9,
                "reasoning_steps": ["checked logs"],
                "action_taken": {
                    "original_code": "old",
                    "fixed_code": "new",
                    "description": "fix",
                },
            }
        )

    def test_clean_json_parses(self):
        result = parse_llm_response(self._valid_json(), HealingAnalysis)
        self.assertEqual(result.failure_type, FailureType.TIMEOUT)

    def test_markdown_fenced_json_parses(self):
        fenced = f"Here is the analysis:\n\n```json\n{self._valid_json()}\n```"
        result = parse_llm_response(fenced, HealingAnalysis)
        self.assertEqual(result.failure_type, FailureType.TIMEOUT)

    def test_json_with_surrounding_text_parses(self):
        surrounded = (
            f"Sure! Here you go:\n{self._valid_json()}\nLet me know if you need more."
        )
        result = parse_llm_response(surrounded, HealingAnalysis)
        self.assertEqual(result.failure_type, FailureType.TIMEOUT)

    def test_empty_response_raises(self):
        with self.assertRaises(ValueError):
            parse_llm_response("", HealingAnalysis)

    def test_invalid_json_raises(self):
        with self.assertRaises(ValueError):
            parse_llm_response("this is not json at all", HealingAnalysis)

    def test_wrong_schema_raises(self):
        """Valid JSON but wrong shape should raise ValueError."""
        wrong = json.dumps({"foo": "bar"})
        with self.assertRaises(ValueError):
            parse_llm_response(wrong, HealingAnalysis)

    def test_confidence_clamping_via_parser(self):
        """Over-confident LLM (1.05) should be clamped to 1.0."""
        payload = json.loads(self._valid_json())
        payload["confidence_score"] = 1.05
        result = parse_llm_response(json.dumps(payload), HealingAnalysis)
        self.assertAlmostEqual(result.confidence_score, 1.0)

    def test_list_code_coercion_via_parser(self):
        """LLM returns original_code as list — should be coerced to string."""
        payload = json.loads(self._valid_json())
        payload["action_taken"]["original_code"] = ["line1", "line2"]
        result = parse_llm_response(json.dumps(payload), HealingAnalysis)
        self.assertEqual(result.action_taken.original_code, "line1\nline2")


if __name__ == "__main__":
    unittest.main()
