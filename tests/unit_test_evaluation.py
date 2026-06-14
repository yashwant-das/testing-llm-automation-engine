"""
Unit tests for Phase 7 — Evaluation Framework.

Coverage:
    TestEvaluationSchemas     — BenchmarkRunConfig, EvaluationResult, BenchmarkRun
    TestMutator               — all 4 mutation types + mutate() dispatcher
    TestGenerationEvaluator   — evaluate_generated_code()
    TestHealingEvaluator      — evaluate_classification(), evaluate_repair()
    TestIntentValidation      — evaluate_test_intent()
    TestGenerationRunner      — run_generation_benchmark() with mocked generator_fn
    TestHealingRunner         — run_healing_benchmark() classification-only + repair modes
"""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

# ---------------------------------------------------------------------------
# Generation
# ---------------------------------------------------------------------------
from benchmarks.generation.runner import (
    GenerationCheck,
    GenerationScenario,
    evaluate_generated_code,
    run_generation_benchmark,
)
from benchmarks.generation.runner import (
    load_dataset as load_gen_dataset,
)

# ---------------------------------------------------------------------------
# Healing
# ---------------------------------------------------------------------------
from benchmarks.healing.runner import (
    HealingCase,
    HealingCheck,
    evaluate_classification,
    evaluate_repair,
    run_healing_benchmark,
)

# ---------------------------------------------------------------------------
# Intent validation
# ---------------------------------------------------------------------------
from benchmarks.intent_validation.runner import (
    evaluate_test_intent,
)

# ---------------------------------------------------------------------------
# Mutations
# ---------------------------------------------------------------------------
from benchmarks.mutations.mutator import (
    MutationResult,
    MutationType,
    apply_assertion_swap,
    apply_import_removal,
    apply_selector_drift,
    apply_timeout_reduction,
    mutate,
)

# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------
from schemas.evaluation import BenchmarkRun, BenchmarkRunConfig, EvaluationResult

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

PROJECT_ROOT = Path(__file__).parent.parent
GEN_DATASET = (
    PROJECT_ROOT / "benchmarks" / "generation" / "fixtures" / "web_scenarios.json"
)
HEAL_DATASET = (
    PROJECT_ROOT / "benchmarks" / "healing" / "fixtures" / "repair_scenarios.json"
)


def _make_config(**overrides) -> BenchmarkRunConfig:
    defaults = dict(
        model="test-model",
        prompt_name="test-prompt",
        prompt_version="1",
        prompt_hash="abc123",
        dataset_version="1.0.0",
        benchmark_type="test",
    )
    defaults.update(overrides)
    return BenchmarkRunConfig(**defaults)


def _passing_ts(url: str = "https://example.com") -> str:
    return f"""import {{ test, expect }} from "@playwright/test";

test("load home page", async ({{ page }}) => {{
  await page.goto("{url}");
  const heading = page.getByRole("heading", {{ name: "Welcome" }});
  await expect(heading).toBeVisible();
}});
"""


# ===========================================================================
# 1. Evaluation Schemas
# ===========================================================================


class TestEvaluationSchemas(unittest.TestCase):
    # --- BenchmarkRunConfig -------------------------------------------------

    def test_config_defaults(self):
        cfg = _make_config()
        self.assertEqual(cfg.temperature, 0.0)
        self.assertEqual(cfg.provider, "unknown")
        self.assertEqual(cfg.benchmark_type, "test")
        self.assertIsNone(cfg.seed)

    def test_config_explicit_fields(self):
        cfg = _make_config(model="gpt-4", provider="openai", temperature=0.5, seed=42)
        self.assertEqual(cfg.model, "gpt-4")
        self.assertEqual(cfg.provider, "openai")
        self.assertEqual(cfg.temperature, 0.5)
        self.assertEqual(cfg.seed, 42)

    # --- EvaluationResult ---------------------------------------------------

    def test_result_defaults(self):
        r = EvaluationResult(example_id="x", passed=True, score=1.0)
        self.assertEqual(r.duration_ms, 0)
        self.assertIsNone(r.error)
        self.assertEqual(r.details, {})

    def test_result_score_bounds_valid(self):
        # Both 0.0 and 1.0 should be accepted
        low = EvaluationResult(example_id="low", passed=False, score=0.0)
        high = EvaluationResult(example_id="high", passed=True, score=1.0)
        self.assertEqual(low.score, 0.0)
        self.assertEqual(high.score, 1.0)

    def test_result_with_error(self):
        r = EvaluationResult(example_id="e1", passed=False, score=0.0, error="boom")
        self.assertEqual(r.error, "boom")
        self.assertFalse(r.passed)

    # --- BenchmarkRun computed fields ---------------------------------------

    def test_run_empty(self):
        run = BenchmarkRun(config=_make_config())
        self.assertEqual(run.total, 0)
        self.assertEqual(run.passed, 0)
        self.assertEqual(run.failed, 0)
        self.assertEqual(run.pass_rate, 0.0)
        self.assertEqual(run.mean_score, 0.0)
        self.assertEqual(run.mean_duration_ms, 0.0)

    def test_run_all_pass(self):
        results = [
            EvaluationResult(example_id="a", passed=True, score=1.0, duration_ms=10),
            EvaluationResult(example_id="b", passed=True, score=0.8, duration_ms=20),
        ]
        run = BenchmarkRun(config=_make_config(), results=results)
        self.assertEqual(run.total, 2)
        self.assertEqual(run.passed, 2)
        self.assertEqual(run.failed, 0)
        self.assertAlmostEqual(run.pass_rate, 1.0)
        self.assertAlmostEqual(run.mean_score, 0.9)
        self.assertAlmostEqual(run.mean_duration_ms, 15.0)

    def test_run_mixed_results(self):
        results = [
            EvaluationResult(example_id="a", passed=True, score=1.0),
            EvaluationResult(example_id="b", passed=False, score=0.0),
            EvaluationResult(example_id="c", passed=False, score=0.5),
        ]
        run = BenchmarkRun(config=_make_config(), results=results)
        self.assertEqual(run.total, 3)
        self.assertEqual(run.passed, 1)
        self.assertEqual(run.failed, 2)
        self.assertAlmostEqual(run.pass_rate, 1 / 3)
        self.assertAlmostEqual(run.mean_score, 0.5)

    def test_run_to_json_structure(self):
        run = BenchmarkRun(
            config=_make_config(),
            results=[EvaluationResult(example_id="x", passed=True, score=1.0)],
        )
        payload = json.loads(run.to_json())
        self.assertIn("config", payload)
        self.assertIn("results", payload)
        self.assertIn("total", payload)
        self.assertIn("pass_rate", payload)
        self.assertIn("mean_score", payload)
        self.assertEqual(payload["total"], 1)

    def test_run_save_report(self):
        run = BenchmarkRun(
            config=_make_config(benchmark_type="generation"),
            results=[EvaluationResult(example_id="x", passed=True, score=1.0)],
        )
        with tempfile.TemporaryDirectory() as tmpdir:
            path = run.save_report(Path(tmpdir), filename="test_report.json")
            self.assertTrue(path.exists())
            payload = json.loads(path.read_text())
            self.assertEqual(payload["total"], 1)

    def test_run_save_report_auto_filename(self):
        run = BenchmarkRun(
            config=_make_config(benchmark_type="healing", model="my-model"),
            results=[],
        )
        with tempfile.TemporaryDirectory() as tmpdir:
            path = run.save_report(Path(tmpdir))
            self.assertTrue(path.exists())
            self.assertTrue(path.name.startswith("healing_my-model_"))
            self.assertTrue(path.name.endswith(".json"))


# ===========================================================================
# 2. Mutator
# ===========================================================================


class TestMutator(unittest.TestCase):
    # --- Pure transformation functions --------------------------------------

    def test_apply_selector_drift_replaces_all(self):
        # Use a simple selector with no nested quotes to avoid escaping issues
        code = (
            "page.locator('[data-testid=submit]')\npage.locator('[data-testid=submit]')"
        )
        result = apply_selector_drift(code, "[data-testid=submit]", "#old-btn")
        self.assertEqual(result.count("#old-btn"), 2)
        self.assertNotIn("[data-testid=submit]", result)

    def test_apply_selector_drift_no_match(self):
        code = "page.locator('[data-testid=other]')"
        result = apply_selector_drift(code, "[data-testid=submit]", "#old-btn")
        self.assertEqual(result, code)  # unchanged

    def test_apply_timeout_reduction_replaces_values(self):
        code = "await page.goto(url, { timeout: 30000 });\nawait page.waitForSelector('#x', { timeout: 10000 });"
        result = apply_timeout_reduction(code, target_ms=500)
        self.assertIn("timeout: 500", result)
        self.assertNotIn("timeout: 30000", result)
        self.assertNotIn("timeout: 10000", result)

    def test_apply_timeout_reduction_no_match(self):
        code = "await page.goto(url);"
        result = apply_timeout_reduction(code, target_ms=500)
        self.assertEqual(result, code)

    def test_apply_import_removal_comma_after(self):
        code = 'import { test, expect } from "@playwright/test";'
        result = apply_import_removal(code, "expect")
        self.assertNotIn("expect", result)
        self.assertIn("test", result)

    def test_apply_import_removal_comma_before(self):
        code = 'import { expect, test } from "@playwright/test";'
        result = apply_import_removal(code, "expect")
        self.assertNotIn("expect", result)
        self.assertIn("test", result)

    def test_apply_import_removal_lone_symbol(self):
        code = 'import { expect } from "@playwright/test";'
        result = apply_import_removal(code, "expect")
        self.assertNotIn("expect", result)

    def test_apply_assertion_swap_replaces_method(self):
        code = "await expect(locator).toBeVisible();"
        result = apply_assertion_swap(code, "toBeVisible", "toBe", "true")
        self.assertIn(".toBe(true)", result)
        self.assertNotIn("toBeVisible", result)

    def test_apply_assertion_swap_no_match(self):
        code = "await expect(locator).toHaveText('hello');"
        result = apply_assertion_swap(code, "toBeVisible", "toBe", "true")
        self.assertEqual(result, code)

    # --- mutate() dispatcher ------------------------------------------------

    def test_mutate_selector_drift_success(self):
        # broken_selector.spec.ts contains locator("#submit-btn") — target that
        fixture = PROJECT_ROOT / "tests" / "fixtures" / "broken_selector.spec.ts"
        result = mutate(
            fixture,
            MutationType.SELECTOR_DRIFT,
            original_selector="#submit-btn",
            broken_selector="#gone",
        )
        self.assertIsInstance(result, MutationResult)
        self.assertTrue(result.success)
        self.assertIn("#gone", result.mutated_code)
        self.assertNotIn("#gone", result.original_code)

    def test_mutate_selector_drift_no_match(self):
        fixture = PROJECT_ROOT / "tests" / "fixtures" / "broken_timeout.spec.ts"
        result = mutate(
            fixture,
            MutationType.SELECTOR_DRIFT,
            original_selector="#nonexistent-selector-xyz",
            broken_selector="#broken",
        )
        self.assertFalse(result.success)  # no change
        self.assertEqual(result.original_code, result.mutated_code)

    def test_mutate_timeout_too_short_success(self):
        fixture = PROJECT_ROOT / "tests" / "fixtures" / "broken_timeout.spec.ts"
        result = mutate(fixture, MutationType.TIMEOUT_TOO_SHORT, target_ms=100)
        self.assertTrue(result.success)
        self.assertIn("timeout: 100", result.mutated_code)

    def test_mutate_missing_import_success(self):
        fixture = PROJECT_ROOT / "tests" / "fixtures" / "broken_assertion.spec.ts"
        result = mutate(fixture, MutationType.MISSING_IMPORT, symbol="expect")
        self.assertTrue(result.success)
        # The import line should not contain "expect" after removal
        import_line = [
            line for line in result.mutated_code.splitlines() if "import" in line
        ]
        self.assertTrue(
            len(import_line) == 0 or "expect" not in import_line[0],
            "expect should be removed from the import",
        )

    def test_mutate_assertion_swap_success(self):
        fixture = PROJECT_ROOT / "tests" / "fixtures" / "broken_timeout.spec.ts"
        result = mutate(
            fixture,
            MutationType.ASSERTION_SWAP,
            from_method="toBeVisible",
            to_method="toBe",
            to_argument="true",
        )
        self.assertTrue(result.success)
        self.assertIn(".toBe(true)", result.mutated_code)

    def test_mutate_file_not_found(self):
        missing = PROJECT_ROOT / "tests" / "fixtures" / "does_not_exist.spec.ts"
        result = mutate(missing, MutationType.TIMEOUT_TOO_SHORT)
        self.assertFalse(result.success)
        self.assertIsNotNone(result.error)

    def test_mutate_result_preserves_source_file(self):
        fixture = PROJECT_ROOT / "tests" / "fixtures" / "broken_timeout.spec.ts"
        result = mutate(fixture, MutationType.TIMEOUT_TOO_SHORT, target_ms=50)
        self.assertEqual(result.source_file, str(fixture))
        self.assertEqual(result.mutation_type, MutationType.TIMEOUT_TOO_SHORT)


# ===========================================================================
# 3. Generation Evaluator
# ===========================================================================


def _make_gen_scenario(
    url: str = "https://example.com",
    must_import: list | None = None,
    must_use_assertions: list | None = None,
    must_not_use_deprecated: list | None = None,
    must_contain_url: bool = True,
    preferred_locators: list | None = None,
) -> GenerationScenario:
    checks = GenerationCheck(
        must_import=must_import or ["@playwright/test"],
        must_use_assertions=must_use_assertions or ["expect"],
        must_not_use_deprecated=must_not_use_deprecated or ["waitForSelector"],
        must_contain_url=must_contain_url,
        preferred_locators=preferred_locators or ["getByRole"],
    )
    return GenerationScenario(
        id="gen-test",
        description="Test scenario",
        url=url,
        feature_description="User submits a form",
        checks=checks,
    )


class TestGenerationEvaluator(unittest.TestCase):
    def test_perfect_code_passes(self):
        scenario = _make_gen_scenario()
        code = _passing_ts()
        result = evaluate_generated_code(code, scenario)
        self.assertTrue(result.passed)
        self.assertGreater(result.score, 0.9)
        self.assertEqual(result.example_id, "gen-test")

    def test_missing_import_fails(self):
        scenario = _make_gen_scenario(must_import=["@playwright/test"])
        code = 'const { test, expect } = require("playwright");\ntest("x", async ({page}) => {});'
        result = evaluate_generated_code(code, scenario)
        self.assertFalse(result.passed)
        self.assertIn(
            "missing-import(@playwright/test)", result.details["checks_failed"]
        )

    def test_missing_assertion_fails(self):
        scenario = _make_gen_scenario(must_use_assertions=["expect"])
        code = 'import { test } from "@playwright/test";\ntest("x", async ({page}) => { await page.goto("https://example.com"); });'
        result = evaluate_generated_code(code, scenario)
        self.assertFalse(result.passed)
        self.assertTrue(any("assertion" in f for f in result.details["checks_failed"]))

    def test_deprecated_api_fails(self):
        scenario = _make_gen_scenario(must_not_use_deprecated=["waitForSelector"])
        code = _passing_ts() + "\nawait page.waitForSelector('#foo');"
        result = evaluate_generated_code(code, scenario)
        self.assertFalse(result.passed)
        self.assertIn("deprecated(waitForSelector)", result.details["checks_failed"])

    def test_missing_url_fails(self):
        scenario = _make_gen_scenario(
            url="https://secret-url.example.com", must_contain_url=True
        )
        code = _passing_ts(url="https://different.example.com")
        result = evaluate_generated_code(code, scenario)
        self.assertFalse(result.passed)
        self.assertTrue(
            any("missing-url" in f for f in result.details["checks_failed"])
        )

    def test_url_check_disabled(self):
        scenario = _make_gen_scenario(
            url="https://secret-url.example.com", must_contain_url=False
        )
        # No URL in code — but check is disabled, so only other checks matter
        code = 'import { test, expect } from "@playwright/test";\ntest("x", async ({page}) => { await expect(page).toBeTruthy(); });'
        result = evaluate_generated_code(code, scenario)
        # No url-related check fired
        self.assertFalse(
            any("missing-url" in f for f in result.details.get("checks_failed", []))
        )

    def test_empty_string_fails(self):
        scenario = _make_gen_scenario()
        result = evaluate_generated_code("", scenario)
        self.assertFalse(result.passed)
        self.assertEqual(result.score, 0.0)
        self.assertIsNotNone(result.error)

    def test_error_string_prefix_fails(self):
        scenario = _make_gen_scenario()
        result = evaluate_generated_code("Error: LLM rate limit exceeded", scenario)
        self.assertFalse(result.passed)
        self.assertEqual(result.score, 0.0)

    def test_llm_error_prefix_fails(self):
        scenario = _make_gen_scenario()
        result = evaluate_generated_code("LLM Error: connection timeout", scenario)
        self.assertFalse(result.passed)
        self.assertEqual(result.score, 0.0)

    def test_preferred_locator_boosts_score(self):
        scenario_with = _make_gen_scenario(preferred_locators=["getByRole"])
        scenario_without = _make_gen_scenario(preferred_locators=[])
        code = _passing_ts()  # contains "getByRole"
        result_with = evaluate_generated_code(code, scenario_with)
        result_without = evaluate_generated_code(code, scenario_without)
        # Both must pass; with-locator should have higher score
        self.assertTrue(result_with.passed)
        self.assertTrue(result_without.passed)
        self.assertGreaterEqual(result_with.score, result_without.score)

    def test_duration_ms_recorded(self):
        scenario = _make_gen_scenario()
        result = evaluate_generated_code(_passing_ts(), scenario, duration_ms=42)
        self.assertEqual(result.duration_ms, 42)

    def test_load_gen_dataset_structure(self):
        dataset = load_gen_dataset(GEN_DATASET)
        self.assertGreater(len(dataset.scenarios), 0)
        self.assertTrue(all(s.id.startswith("gen-") for s in dataset.scenarios))
        self.assertTrue(dataset.version)


# ===========================================================================
# 4. Healing Evaluator
# ===========================================================================


def _make_healing_case(
    expected_type: str | None = "LOCATOR_NOT_FOUND",
    must_fix: str | None = "locator('#old')",
    must_contain: list | None = None,
    code_must_change: bool = True,
) -> HealingCase:
    return HealingCase(
        id="heal-test",
        description="Test case",
        broken_test_file="tests/fixtures/broken_selector.spec.ts",
        injected_failure_type="LOCATOR_NOT_FOUND",
        error_log="locator resolved to 0 elements",
        checks=HealingCheck(
            expected_failure_type=expected_type,
            must_fix_pattern=must_fix,
            fixed_code_must_contain=must_contain or ["data-testid"],
            code_must_change=code_must_change,
        ),
    )


BROKEN_CODE = 'page.locator("#old")'
REPAIRED_CODE = 'page.locator("[data-testid=\\"submit\\"]")'


class TestHealingEvaluator(unittest.TestCase):
    # --- evaluate_classification ---------------------------------------------

    def test_classify_correct_type_returns_true(self):
        case = _make_healing_case(expected_type="LOCATOR_NOT_FOUND")
        self.assertTrue(evaluate_classification(case, "LOCATOR_NOT_FOUND"))

    def test_classify_wrong_type_returns_false(self):
        case = _make_healing_case(expected_type="LOCATOR_NOT_FOUND")
        self.assertFalse(evaluate_classification(case, "TIMEOUT"))

    def test_classify_no_expected_type_always_true(self):
        case = _make_healing_case(expected_type=None)
        self.assertTrue(evaluate_classification(case, "ANYTHING"))
        self.assertTrue(evaluate_classification(case, ""))

    # --- evaluate_repair -----------------------------------------------------

    def test_repair_all_checks_pass(self):
        case = _make_healing_case()
        result = evaluate_repair(
            case,
            BROKEN_CODE,
            REPAIRED_CODE,
            classified_type="LOCATOR_NOT_FOUND",
            duration_ms=55,
        )
        self.assertTrue(result.passed)
        self.assertEqual(result.score, 1.0)
        self.assertEqual(result.duration_ms, 55)

    def test_repair_wrong_classification_fails(self):
        case = _make_healing_case(expected_type="LOCATOR_NOT_FOUND")
        result = evaluate_repair(
            case,
            BROKEN_CODE,
            REPAIRED_CODE,
            classified_type="TIMEOUT",
        )
        self.assertFalse(result.passed)
        self.assertTrue(
            any("classification" in f for f in result.details["checks_failed"])
        )

    def test_repair_code_not_modified_fails(self):
        case = _make_healing_case(code_must_change=True)
        result = evaluate_repair(
            case,
            BROKEN_CODE,
            BROKEN_CODE,  # same as original
            classified_type="LOCATOR_NOT_FOUND",
        )
        self.assertFalse(result.passed)
        self.assertIn("code-not-modified", result.details["checks_failed"])

    def test_repair_must_fix_pattern_still_present_fails(self):
        # BROKEN_CODE uses double-quoted selector — match that exact pattern
        case = _make_healing_case(must_fix='locator("#old")', must_contain=[])
        result = evaluate_repair(
            case,
            BROKEN_CODE,
            BROKEN_CODE + " extra content",  # pattern still present
            classified_type="LOCATOR_NOT_FOUND",
        )
        self.assertFalse(result.passed)
        self.assertTrue(any("not-fixed" in f for f in result.details["checks_failed"]))

    def test_repair_must_contain_missing_fails(self):
        case = _make_healing_case(must_fix=None, must_contain=["getByRole"])
        result = evaluate_repair(
            case,
            BROKEN_CODE,
            REPAIRED_CODE,  # does not contain getByRole
            classified_type="LOCATOR_NOT_FOUND",
        )
        self.assertFalse(result.passed)
        self.assertTrue(any("missing" in f for f in result.details["checks_failed"]))

    def test_repair_result_has_classified_type_in_details(self):
        case = _make_healing_case()
        result = evaluate_repair(
            case, BROKEN_CODE, REPAIRED_CODE, classified_type="LOCATOR_NOT_FOUND"
        )
        self.assertEqual(result.details["classified_type"], "LOCATOR_NOT_FOUND")


# ===========================================================================
# 5. Intent Validation
# ===========================================================================

_GOOD_CODE = """import { test, expect } from "@playwright/test";

test("submit login form", async ({ page }) => {
  await page.goto("https://login.example.com");
  await page.getByLabel("Username").fill("alice");
  await page.getByRole("button", { name: "Submit" }).click();
  await expect(page.getByText("Welcome")).toBeVisible();
});
"""


class TestIntentValidation(unittest.TestCase):
    def test_perfect_code_passes_all_checks(self):
        result = evaluate_test_intent(
            _GOOD_CODE,
            "https://login.example.com",
            "User submits the login form",
            example_id="iv-001",
        )
        self.assertTrue(result.passed)
        self.assertGreater(result.score, 0.9)
        self.assertEqual(result.details["checks_failed"], [])

    def test_missing_test_block_fails(self):
        # Replace "test(" with a different function name so the check doesn't match
        code = _GOOD_CODE.replace("test(", "suite(")
        result = evaluate_test_intent(code, "https://login.example.com", "login form")
        self.assertFalse(result.passed)
        self.assertIn("no-test-block", result.details["checks_failed"])

    def test_missing_expect_assertion_fails(self):
        # Replace "expect(" with a different call so the check doesn't match
        code = _GOOD_CODE.replace("expect(", "assert(")
        result = evaluate_test_intent(code, "https://login.example.com", "login form")
        self.assertFalse(result.passed)
        self.assertIn("no-expect-assertion", result.details["checks_failed"])

    def test_missing_async_await_fails(self):
        code = _GOOD_CODE.replace("async ", "").replace("await ", "")
        result = evaluate_test_intent(code, "https://login.example.com", "login form")
        self.assertFalse(result.passed)
        self.assertIn("missing-async-await", result.details["checks_failed"])

    def test_missing_url_fails(self):
        result = evaluate_test_intent(
            _GOOD_CODE,
            "https://totally-different.example.com",
            "login form",
        )
        self.assertFalse(result.passed)
        self.assertTrue(
            any("missing-url" in f for f in result.details["checks_failed"])
        )

    def test_url_in_code_passes_url_check(self):
        result = evaluate_test_intent(
            _GOOD_CODE,
            "https://login.example.com",
            "login form",
        )
        self.assertIn("url-present", result.details["checks_passed"])

    def test_test_name_reflects_feature_keyword(self):
        # "login" keyword should match "submit login form" test name
        result = evaluate_test_intent(
            _GOOD_CODE,
            "https://login.example.com",
            "User should be able to login securely",
        )
        self.assertTrue(
            any(
                "test-name-reflects-intent" in p
                for p in result.details["checks_passed"]
            )
        )

    def test_missing_navigation_fails(self):
        # Replace "page.goto(" with a different call so the check doesn't match
        code = _GOOD_CODE.replace("page.goto(", "navigate(")
        result = evaluate_test_intent(code, "https://login.example.com", "login")
        self.assertFalse(result.passed)
        self.assertIn("no-page-goto", result.details["checks_failed"])

    def test_empty_code_fails(self):
        result = evaluate_test_intent("", "https://example.com", "some feature")
        self.assertFalse(result.passed)
        self.assertEqual(result.score, 0.0)

    def test_error_prefix_fails_immediately(self):
        result = evaluate_test_intent(
            "Error: LLM unavailable", "https://example.com", "some feature"
        )
        self.assertFalse(result.passed)
        self.assertEqual(result.score, 0.0)
        self.assertIsNotNone(result.error)

    def test_example_id_recorded(self):
        result = evaluate_test_intent(
            _GOOD_CODE,
            "https://login.example.com",
            "login form",
            example_id="custom-id-99",
        )
        self.assertEqual(result.example_id, "custom-id-99")

    def test_duration_ms_recorded(self):
        result = evaluate_test_intent(
            _GOOD_CODE,
            "https://login.example.com",
            "login form",
            duration_ms=77,
        )
        self.assertEqual(result.duration_ms, 77)


# ===========================================================================
# 6. Generation Runner (with mocked generator_fn)
# ===========================================================================


class TestGenerationRunner(unittest.TestCase):
    def test_run_all_pass(self):
        """Mock generator always returns perfect code; all scenarios should pass."""

        def perfect_gen(url: str, feature: str) -> str:
            return _passing_ts(url)

        run = run_generation_benchmark(
            GEN_DATASET,
            perfect_gen,
            _make_config(benchmark_type="generation"),
            scenario_ids=["gen-001"],
        )
        self.assertEqual(run.total, 1)
        self.assertEqual(run.passed, 1)
        self.assertAlmostEqual(run.pass_rate, 1.0)

    def test_run_all_fail_on_empty_output(self):
        """Mock generator returns empty string; all scenarios should fail."""
        run = run_generation_benchmark(
            GEN_DATASET,
            lambda url, feat: "",
            _make_config(benchmark_type="generation"),
        )
        self.assertEqual(run.passed, 0)
        self.assertEqual(run.failed, run.total)

    def test_run_scenario_ids_filter(self):
        """scenario_ids should limit which scenarios are evaluated."""
        dataset = load_gen_dataset(GEN_DATASET)
        all_ids = [s.id for s in dataset.scenarios]
        subset = all_ids[:2]

        run = run_generation_benchmark(
            GEN_DATASET,
            lambda url, feat: "",
            _make_config(benchmark_type="generation"),
            scenario_ids=subset,
        )
        self.assertEqual(run.total, len(subset))

    def test_run_generator_exception_becomes_failure(self):
        """If generator_fn raises, the result should be a failed EvaluationResult."""

        def bad_gen(url, feat):
            raise RuntimeError("upstream failure")

        run = run_generation_benchmark(
            GEN_DATASET,
            bad_gen,
            _make_config(benchmark_type="generation"),
            scenario_ids=["gen-001"],
        )
        self.assertEqual(run.total, 1)
        self.assertFalse(run.results[0].passed)
        self.assertEqual(run.results[0].score, 0.0)

    def test_run_returns_benchmarkrun_type(self):
        run = run_generation_benchmark(
            GEN_DATASET,
            lambda url, feat: "",
            _make_config(),
            scenario_ids=["gen-001"],
        )
        self.assertIsInstance(run, BenchmarkRun)


# ===========================================================================
# 7. Healing Runner (with mocked healer_fn)
# ===========================================================================


class TestHealingRunner(unittest.TestCase):
    # ── Classification-only mode ─────────────────────────────────────────────

    def test_classification_only_all_pass(self):
        """Real heuristic classifier should correctly classify all 4 fixture cases."""
        run = run_healing_benchmark(
            HEAL_DATASET,
            PROJECT_ROOT,
            _make_config(benchmark_type="healing"),
        )
        self.assertEqual(run.total, 4)
        self.assertEqual(
            run.passed,
            4,
            msg=f"Failing cases: {[r for r in run.results if not r.passed]}",
        )

    def test_classification_only_mode_label_in_details(self):
        """Classification-only results should carry mode='classification-only'."""
        run = run_healing_benchmark(
            HEAL_DATASET,
            PROJECT_ROOT,
            _make_config(benchmark_type="healing"),
            case_ids=["heal-001"],
        )
        self.assertEqual(run.total, 1)
        self.assertEqual(run.results[0].details.get("mode"), "classification-only")

    def test_case_ids_filter(self):
        run = run_healing_benchmark(
            HEAL_DATASET,
            PROJECT_ROOT,
            _make_config(benchmark_type="healing"),
            case_ids=["heal-002"],
        )
        self.assertEqual(run.total, 1)
        self.assertEqual(run.results[0].example_id, "heal-002")

    def test_returns_benchmarkrun_type(self):
        run = run_healing_benchmark(
            HEAL_DATASET,
            PROJECT_ROOT,
            _make_config(benchmark_type="healing"),
            case_ids=["heal-001"],
        )
        self.assertIsInstance(run, BenchmarkRun)

    # ── Full repair mode ─────────────────────────────────────────────────────

    def test_full_repair_mode_with_perfect_healer(self):
        """A healer that always produces the expected repaired code should pass."""

        def perfect_healer(code: str, error_log: str) -> str:
            # broken_selector.spec.ts uses "#submit-btn" (double quotes) — replace it
            return code.replace("#submit-btn", '[data-testid="submit"]')

        run = run_healing_benchmark(
            HEAL_DATASET,
            PROJECT_ROOT,
            _make_config(benchmark_type="healing"),
            healer_fn=perfect_healer,
            case_ids=["heal-001"],
        )
        self.assertEqual(run.total, 1)
        self.assertTrue(run.results[0].passed)

    def test_full_repair_mode_with_no_op_healer(self):
        """A healer that returns the original code unchanged should fail code-must-change."""

        def no_op_healer(code: str, error_log: str) -> str:
            return code  # no change

        run = run_healing_benchmark(
            HEAL_DATASET,
            PROJECT_ROOT,
            _make_config(benchmark_type="healing"),
            healer_fn=no_op_healer,
            case_ids=["heal-001"],
        )
        self.assertEqual(run.total, 1)
        self.assertFalse(run.results[0].passed)

    def test_full_repair_mode_healer_exception_becomes_failure(self):
        """A healer that raises should result in a failed, non-crashing EvaluationResult."""

        def crashing_healer(code: str, error_log: str) -> str:
            raise RuntimeError("repair service unavailable")

        run = run_healing_benchmark(
            HEAL_DATASET,
            PROJECT_ROOT,
            _make_config(benchmark_type="healing"),
            healer_fn=crashing_healer,
            case_ids=["heal-001"],
        )
        self.assertEqual(run.total, 1)
        self.assertFalse(run.results[0].passed)
        self.assertIsNotNone(run.results[0].error)

    def test_missing_fixture_file_handled_gracefully(self):
        """If the broken_test_file doesn't exist, the runner should record a failure without crashing."""
        run = run_healing_benchmark(
            HEAL_DATASET,
            Path("/nonexistent/project/root"),
            _make_config(benchmark_type="healing"),
            case_ids=["heal-001"],
        )
        self.assertEqual(run.total, 1)
        self.assertFalse(run.results[0].passed)
        self.assertIsNotNone(run.results[0].error)


if __name__ == "__main__":
    unittest.main()
