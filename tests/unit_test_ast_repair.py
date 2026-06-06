"""
Unit and integration tests for the Phase 5 AST-based repair system.

Test structure:
  TestRepairStrategy       — RepairStrategy enum and HealingAction.repair_strategy field
  TestApplyFixRouting      — apply_fix() routes to AST or string based on strategy
                             (subprocess mocked — no live Node.js calls)
  TestAstRepairIntegration — live Node.js calls via ast_repair.js
                             (require Node.js + ts-morph in node_modules)
  TestStringFallback       — _apply_string_fix() still passes all Phase 4 cases
                             (no regression)
"""

import json
import subprocess
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from schemas.healing import (
    Evidence,
    HealingAction,
    HealingDecision,
    RepairStrategy,
)
from schemas.shared import FailureType
from src.healing.repair import _apply_ast_fix, _apply_string_fix, apply_fix

PROJECT_ROOT = Path(__file__).resolve().parent.parent
FIXTURES_DIR = PROJECT_ROOT / "tests" / "fixtures"
AST_SCRIPT = PROJECT_ROOT / "scripts" / "ast_repair.js"


# ── helpers ───────────────────────────────────────────────────────────────────


def _make_decision(
    *,
    original_code: str = "",
    fixed_code: str = "",
    description: str = "",
    strategy: RepairStrategy = RepairStrategy.STRING_REPLACE,
    failure_type: FailureType = FailureType.LOCATOR_DRIFT,
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
            repair_strategy=strategy,
        ),
    )


def _ast_available() -> bool:
    """Return True if Node.js and ts-morph are available."""
    try:
        r = subprocess.run(
            ["node", "-e", "require('ts-morph'); process.exit(0);"],
            capture_output=True,
            timeout=10,
            cwd=str(PROJECT_ROOT),
        )
        return r.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False


SKIP_IF_NO_NODE = unittest.skipUnless(_ast_available(), "Node.js + ts-morph required")


# ── TestRepairStrategy ────────────────────────────────────────────────────────


class TestRepairStrategy(unittest.TestCase):
    def test_enum_values(self):
        self.assertEqual(RepairStrategy.STRING_REPLACE.value, "string_replace")
        self.assertEqual(RepairStrategy.SELECTOR_REPLACE.value, "selector_replace")
        self.assertEqual(RepairStrategy.IMPORT_ADD.value, "import_add")
        self.assertEqual(RepairStrategy.TIMEOUT_ADJUST.value, "timeout_adjust")
        self.assertEqual(RepairStrategy.ROLE_ARGUMENT.value, "role_argument")
        self.assertEqual(RepairStrategy.ASSERTION_SWAP.value, "assertion_swap")

    def test_healing_action_default_strategy_is_string_replace(self):
        action = HealingAction(
            original_code="old", fixed_code="new", description="test"
        )
        self.assertEqual(action.repair_strategy, RepairStrategy.STRING_REPLACE)

    def test_healing_action_accepts_strategy(self):
        action = HealingAction(
            original_code="old",
            fixed_code="new",
            description="test",
            repair_strategy=RepairStrategy.SELECTOR_REPLACE,
        )
        self.assertEqual(action.repair_strategy, RepairStrategy.SELECTOR_REPLACE)

    def test_healing_action_coerces_string_strategy(self):
        action = HealingAction(
            original_code="old",
            fixed_code="new",
            description="test",
            repair_strategy="selector_replace",
        )
        self.assertEqual(action.repair_strategy, RepairStrategy.SELECTOR_REPLACE)

    def test_healing_action_none_strategy_defaults_to_string_replace(self):
        action = HealingAction(
            original_code="old",
            fixed_code="new",
            description="test",
            repair_strategy=None,
        )
        self.assertEqual(action.repair_strategy, RepairStrategy.STRING_REPLACE)

    def test_healing_action_survives_json_round_trip(self):
        action = HealingAction(
            original_code="old",
            fixed_code="new",
            description="test",
            repair_strategy=RepairStrategy.IMPORT_ADD,
        )
        dumped = action.model_dump_json()
        loaded = HealingAction.model_validate_json(dumped)
        self.assertEqual(loaded.repair_strategy, RepairStrategy.IMPORT_ADD)

    def test_healing_action_missing_strategy_in_json_defaults_to_string_replace(self):
        """Old artifact JSON without repair_strategy should load correctly."""
        payload = json.dumps(
            {"original_code": "old", "fixed_code": "new", "description": "test"}
        )
        action = HealingAction.model_validate_json(payload)
        self.assertEqual(action.repair_strategy, RepairStrategy.STRING_REPLACE)

    def test_is_str_enum_for_json_serialization(self):
        """RepairStrategy must be a str subclass so Pydantic serialises it as a plain string."""
        self.assertIsInstance(RepairStrategy.SELECTOR_REPLACE, str)
        # .value gives the raw string; Pydantic uses this for JSON serialisation
        self.assertEqual(RepairStrategy.SELECTOR_REPLACE.value, "selector_replace")


# ── TestApplyFixRouting ───────────────────────────────────────────────────────


class TestApplyFixRouting(unittest.TestCase):
    """apply_fix() routing — subprocess mocked, no live Node.js calls."""

    def _mock_ast_success(self, new_source: str, changes: int = 1) -> MagicMock:
        m = MagicMock()
        m.returncode = 0
        m.stdout = json.dumps(
            {"success": True, "source": new_source, "changes": changes}
        )
        m.stderr = ""
        return m

    def _mock_ast_failure(self, error: str = "no match") -> MagicMock:
        m = MagicMock()
        m.returncode = 0
        m.stdout = json.dumps(
            {"success": False, "source": "original", "changes": 0, "error": error}
        )
        m.stderr = ""
        return m

    @patch("src.healing.repair.subprocess.run")
    def test_string_replace_strategy_skips_subprocess(self, mock_run):
        decision = _make_decision(
            original_code="await page.click('#old');",
            fixed_code="await page.click('#new');",
            strategy=RepairStrategy.STRING_REPLACE,
        )
        current = "    await page.click('#old');"
        result = apply_fix("test.ts", current, decision)
        mock_run.assert_not_called()
        self.assertIn("#new", result)

    @patch("src.healing.repair.subprocess.run")
    def test_ast_strategy_calls_subprocess(self, mock_run):
        mock_run.return_value = self._mock_ast_success("modified source")
        decision = _make_decision(
            original_code="page.locator('#old')",
            fixed_code="page.locator('#new')",
            strategy=RepairStrategy.SELECTOR_REPLACE,
        )
        result = apply_fix("test.ts", "original source", decision)
        mock_run.assert_called_once()
        self.assertEqual(result, "modified source")

    @patch("src.healing.repair.subprocess.run")
    def test_ast_failure_falls_back_to_string(self, mock_run):
        mock_run.return_value = self._mock_ast_failure()
        decision = _make_decision(
            original_code="await page.click('#old');",
            fixed_code="await page.click('#new');",
            strategy=RepairStrategy.SELECTOR_REPLACE,
        )
        current = "    await page.click('#old');"
        result = apply_fix("test.ts", current, decision)
        # AST failed → string fallback applied
        self.assertIn("#new", result)

    @patch("src.healing.repair.subprocess.run")
    def test_ast_zero_changes_falls_back_to_string(self, mock_run):
        original = "    await page.click('#old');"
        # Node.js returns same source with 0 changes
        m = MagicMock()
        m.returncode = 0
        m.stdout = json.dumps({"success": True, "source": original, "changes": 0})
        m.stderr = ""
        mock_run.return_value = m
        decision = _make_decision(
            original_code="await page.click('#old');",
            fixed_code="await page.click('#new');",
            strategy=RepairStrategy.SELECTOR_REPLACE,
        )
        result = apply_fix("test.ts", original, decision)
        self.assertIn("#new", result)

    @patch(
        "src.healing.repair.subprocess.run",
        side_effect=subprocess.TimeoutExpired("node", 30),
    )
    def test_ast_timeout_falls_back_to_string(self, _mock_run):
        decision = _make_decision(
            original_code="await page.click('#old');",
            fixed_code="await page.click('#new');",
            strategy=RepairStrategy.SELECTOR_REPLACE,
        )
        current = "    await page.click('#old');"
        result = apply_fix("test.ts", current, decision)
        self.assertIn("#new", result)

    @patch("src.healing.repair.subprocess.run", side_effect=FileNotFoundError())
    def test_node_not_found_falls_back_to_string(self, _mock_run):
        decision = _make_decision(
            original_code="await page.click('#old');",
            fixed_code="await page.click('#new');",
            strategy=RepairStrategy.SELECTOR_REPLACE,
        )
        current = "    await page.click('#old');"
        result = apply_fix("test.ts", current, decision)
        self.assertIn("#new", result)

    @patch("src.healing.repair.subprocess.run")
    def test_subprocess_input_contains_strategy_and_source(self, mock_run):
        mock_run.return_value = self._mock_ast_success("x")
        decision = _make_decision(
            original_code="page.locator('#old')",
            fixed_code="page.locator('#new')",
            strategy=RepairStrategy.SELECTOR_REPLACE,
        )
        apply_fix("test.ts", "source code here", decision)
        call_kwargs = mock_run.call_args[1]
        payload = json.loads(call_kwargs["input"])
        self.assertEqual(payload["strategy"], "selector_replace")
        self.assertEqual(payload["source"], "source code here")
        self.assertEqual(payload["original_code"], "page.locator('#old')")
        self.assertEqual(payload["fixed_code"], "page.locator('#new')")


# ── TestAstRepairIntegration ──────────────────────────────────────────────────


@SKIP_IF_NO_NODE
class TestAstRepairIntegration(unittest.TestCase):
    """Live Node.js + ts-morph integration tests using fixture TypeScript files."""

    def _run_ast(
        self, strategy: RepairStrategy, source: str, original_code: str, fixed_code: str
    ) -> dict:
        decision = _make_decision(
            original_code=original_code,
            fixed_code=fixed_code,
            strategy=strategy,
        )
        result = _apply_ast_fix(source, decision)
        return result

    # selector_replace ────────────────────────────────────────────────────────

    def test_selector_replace_single_occurrence(self):
        source = "await page.locator('#old-btn').click();"
        result = self._run_ast(
            RepairStrategy.SELECTOR_REPLACE,
            source,
            "page.locator('#old-btn')",
            "page.locator('#new-btn')",
        )
        self.assertIn("#new-btn", result)
        self.assertNotIn("#old-btn", result)

    def test_selector_replace_all_occurrences(self):
        """AST repair replaces EVERY occurrence, not just the first."""
        source = (
            "await page.locator('#submit').waitFor();\n"
            "await page.locator('#submit').click();\n"
            "await page.locator('#submit').isVisible();"
        )
        result = self._run_ast(
            RepairStrategy.SELECTOR_REPLACE,
            source,
            "page.locator('#submit')",
            "page.locator('[data-testid=\"submit\"]')",
        )
        self.assertEqual(result.count("#submit"), 0)
        self.assertEqual(result.count('[data-testid="submit"]'), 3)

    def test_selector_replace_fixture_file(self):
        source = FIXTURES_DIR.joinpath("broken_selector.spec.ts").read_text()
        result = self._run_ast(
            RepairStrategy.SELECTOR_REPLACE,
            source,
            "page.locator('#submit-btn')",
            "page.locator('[data-testid=\"submit\"]')",
        )
        # Both locator CALLS must be replaced (comment lines are untouched — that's correct)
        self.assertNotIn("locator('#submit-btn')", result)
        # Two locator('#submit-btn') calls were replaced; comment line is unchanged
        self.assertEqual(result.count("locator('[data-testid=\"submit\"]')"), 2)

    def test_selector_replace_get_by_text(self):
        source = "await page.getByText('Submit Form').click();"
        result = self._run_ast(
            RepairStrategy.SELECTOR_REPLACE,
            source,
            "page.getByText('Submit Form')",
            "page.getByText('Submit Result')",
        )
        self.assertIn("Submit Result", result)
        self.assertNotIn("Submit Form", result)

    def test_selector_replace_no_match_returns_original(self):
        source = "await page.locator('#other').click();"
        result = self._run_ast(
            RepairStrategy.SELECTOR_REPLACE,
            source,
            "page.locator('#nonexistent')",
            "page.locator('#new')",
        )
        self.assertEqual(result, source)

    # import_add ──────────────────────────────────────────────────────────────

    def test_import_add_inserts_at_top(self):
        source = "test('x', async ({ page }) => { await page.goto('url'); });"
        result = self._run_ast(
            RepairStrategy.IMPORT_ADD,
            source,
            "",
            "import { expect } from '@playwright/test';",
        )
        self.assertIn("import { expect }", result)
        self.assertTrue(result.index("import") < result.index("test("))

    def test_import_add_fixture_file(self):
        source = FIXTURES_DIR.joinpath("broken_import.spec.ts").read_text()
        result = self._run_ast(
            RepairStrategy.IMPORT_ADD,
            source,
            "",
            "import { expect } from '@playwright/test';",
        )
        self.assertIn("expect", result)
        # Should now have two named imports from @playwright/test
        self.assertIn("@playwright/test", result)

    def test_import_add_skips_duplicate(self):
        source = "import { test, expect } from '@playwright/test';\ntest('x', async () => {});"
        result = self._run_ast(
            RepairStrategy.IMPORT_ADD,
            source,
            "",
            "import { expect } from '@playwright/test';",
        )
        # Should be unchanged (or merge silently)
        self.assertEqual(result.count("@playwright/test"), 1)

    # timeout_adjust ──────────────────────────────────────────────────────────

    def test_timeout_adjust_updates_property(self):
        source = (
            "await page.goto('url', { timeout: 5000 });\n"
            "await page.waitForSelector('#el', { timeout: 5000 });"
        )
        result = self._run_ast(
            RepairStrategy.TIMEOUT_ADJUST,
            source,
            "{ timeout: 5000 }",
            "{ timeout: 30000 }",
        )
        self.assertNotIn("5000", result)
        self.assertEqual(result.count("30000"), 2)

    def test_timeout_adjust_fixture_file(self):
        source = FIXTURES_DIR.joinpath("broken_timeout.spec.ts").read_text()
        result = self._run_ast(
            RepairStrategy.TIMEOUT_ADJUST,
            source,
            "{ timeout: 5000 }",
            "{ timeout: 30000 }",
        )
        # timeout: 5000 must be gone; the comment may mention "5000ms" (that's fine)
        self.assertNotIn("timeout: 5000", result)
        self.assertIn("timeout: 30000", result)

    # assertion_swap ──────────────────────────────────────────────────────────

    def test_assertion_swap_renames_method(self):
        source = "await expect(heading).toBe('Hello');"
        result = self._run_ast(
            RepairStrategy.ASSERTION_SWAP,
            source,
            "expect(heading).toBe('Hello')",
            "expect(heading).toHaveText('Hello')",
        )
        self.assertIn("toHaveText", result)
        self.assertNotIn(".toBe(", result)

    def test_assertion_swap_fixture_file(self):
        source = FIXTURES_DIR.joinpath("broken_assertion.spec.ts").read_text()
        result = self._run_ast(
            RepairStrategy.ASSERTION_SWAP,
            source,
            "expect(heading).toBe('Example Domain')",
            "expect(heading).toHaveText('Example Domain')",
        )
        self.assertIn("toHaveText", result)

    # role_argument ───────────────────────────────────────────────────────────

    def test_role_argument_updates_name(self):
        source = "await page.getByRole('button', { name: 'Submit Form' }).click();"
        result = self._run_ast(
            RepairStrategy.ROLE_ARGUMENT,
            source,
            "getByRole('button', { name: 'Submit Form' })",
            "getByRole('button', { name: 'Submit Result' })",
        )
        self.assertIn("Submit Result", result)
        self.assertNotIn("Submit Form", result)

    # error handling ──────────────────────────────────────────────────────────

    @patch("src.healing.repair.subprocess.run")
    def test_unknown_strategy_node_returns_original(self, mock_run):
        """When Node.js reports an unknown strategy, _apply_ast_fix returns original."""
        m = MagicMock()
        m.returncode = 0
        m.stdout = json.dumps(
            {
                "success": False,
                "source": "const x = 1;",
                "changes": 0,
                "error": "Unknown strategy: bad_strategy",
            }
        )
        m.stderr = ""
        mock_run.return_value = m

        source = "const x = 1;"
        decision = _make_decision(
            original_code="x",
            fixed_code="y",
            strategy=RepairStrategy.SELECTOR_REPLACE,
        )
        result = _apply_ast_fix(source, decision)
        self.assertEqual(result, source)

    def test_empty_source_returns_empty(self):
        result = self._run_ast(
            RepairStrategy.SELECTOR_REPLACE,
            "",
            "page.locator('#old')",
            "page.locator('#new')",
        )
        self.assertEqual(result, "")


# ── TestStringFallback (regression) ──────────────────────────────────────────


class TestStringFallback(unittest.TestCase):
    """All Phase 4 string repair tests must continue to pass (no regression)."""

    def test_fuzzy_match_whitespace(self):
        current_code = """
        // comment
        await page.click('#wrong');
        // next line
        """
        decision = _make_decision(
            original_code="await page.click('#wrong');",
            fixed_code="await page.click('#right');",
            strategy=RepairStrategy.STRING_REPLACE,
        )
        new_code = apply_fix("dummy.ts", current_code, decision)
        self.assertIn("#right", new_code)
        self.assertNotIn("#wrong", new_code)

    def test_multiline_indentation_preservation(self):
        current_code = """
    test('foo', async ({ page }) => {
        await page.goto('url');
        await page.click('#wrong');
    });
"""
        decision = _make_decision(
            original_code="await page.goto('url');\nawait page.click('#wrong');",
            fixed_code="await page.goto('url');\nawait page.click('#right');",
            strategy=RepairStrategy.STRING_REPLACE,
        )
        new_code = apply_fix("dummy.ts", current_code, decision)
        self.assertIn("#right", new_code)

    def test_empty_target_returns_original(self):
        current = "some code"
        decision = _make_decision(
            original_code="",
            fixed_code="replacement",
            strategy=RepairStrategy.STRING_REPLACE,
        )
        result = apply_fix("dummy.ts", current, decision)
        self.assertEqual(result, current)

    def test_no_match_returns_original(self):
        current = "await page.click('#different');"
        decision = _make_decision(
            original_code="await page.click('#nonexistent');",
            fixed_code="await page.click('#new');",
            strategy=RepairStrategy.STRING_REPLACE,
        )
        result = apply_fix("dummy.ts", current, decision)
        self.assertEqual(result, current)

    def test_apply_string_fix_internal_function(self):
        """_apply_string_fix is directly callable for unit testing."""
        decision = _make_decision(
            original_code="const x = 1;",
            fixed_code="const x = 2;",
            strategy=RepairStrategy.STRING_REPLACE,
        )
        result = _apply_string_fix("const x = 1;", decision)
        self.assertEqual(result, "const x = 2;")


if __name__ == "__main__":
    unittest.main()
