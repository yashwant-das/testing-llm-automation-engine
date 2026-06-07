import unittest

from schemas.healing import Evidence, HealingAction, HealingDecision
from schemas.shared import FailureType
from src.healing.repair import apply_fix


class TestFixApplication(unittest.TestCase):
    def test_fuzzy_match_whitespace(self):
        current_code = """
        // comment
        await page.click('#wrong');
        // next line
        """

        # LLM returns target with different surrounding whitespace or no indentation
        target = "await page.click('#wrong');"
        replacement = "await page.click('#right');"

        # Mock Decision
        decision = HealingDecision(
            test_file="dummy.ts",
            failure_type=FailureType.UNKNOWN,
            failure_summary="",
            evidence=Evidence(error_log=""),
            hypothesis="",
            confidence_score=1.0,
            reasoning_steps=[],
            action_taken=HealingAction(
                original_code=target, fixed_code=replacement, description=""
            ),
        )

        new_code = apply_fix("dummy.ts", current_code, decision)

        expected = """
        // comment
        await page.click('#right');
        // next line
        """

        self.assertEqual(new_code.strip(), expected.strip())

    def test_multiline_indentation_preservation(self):
        current_code = """
    test('foo', async ({ page }) => {
        await page.goto('url');
        await page.click('#wrong');
    });
"""
        target = """await page.goto('url');
await page.click('#wrong');"""

        replacement = """await page.goto('url');
await page.click('#right');"""

        decision = HealingDecision(
            test_file="dummy.ts",
            failure_type=FailureType.UNKNOWN,
            failure_summary="",
            evidence=Evidence(error_log=""),
            hypothesis="",
            confidence_score=1.0,
            reasoning_steps=[],
            action_taken=HealingAction(
                original_code=target, fixed_code=replacement, description=""
            ),
        )

        new_code = apply_fix("dummy.ts", current_code, decision)

        # Should preserve 4-space indentation
        expected = """
    test('foo', async ({ page }) => {
        await page.goto('url');
        await page.click('#right');
    });
"""
        self.assertEqual(new_code.strip(), expected.strip())

    def test_nested_indentation_preservation(self):
        current_code = """
    test('nested', async ({ page }) => {
        await page.click('#wrong');
        // extra comments
    });
"""
        target = "await page.click('#wrong');"
        # Replacement has nested if statement
        replacement = """await page.click('#right');
if (success) {
    await page.click('#done');
}"""

        decision = HealingDecision(
            test_file="dummy.ts",
            failure_type=FailureType.UNKNOWN,
            failure_summary="",
            evidence=Evidence(error_log=""),
            hypothesis="",
            confidence_score=1.0,
            reasoning_steps=[],
            action_taken=HealingAction(
                original_code=target, fixed_code=replacement, description=""
            ),
        )

        new_code = apply_fix("dummy.ts", current_code, decision)

        expected = """
    test('nested', async ({ page }) => {
        await page.click('#right');
        if (success) {
            await page.click('#done');
        }
        // extra comments
    });
"""
        self.assertEqual(new_code.strip(), expected.strip())

    def test_extract_url_from_code(self):
        from src.healing.evidence import extract_url_from_code

        code_single = "await page.goto('https://example.com/foo');"
        code_double = 'await page.goto("https://example.com/bar");'
        code_backtick = "await page.goto(`https://example.com/baz`);"
        code_none = "await page.click('#btn');"

        self.assertEqual(extract_url_from_code(code_single), "https://example.com/foo")
        self.assertEqual(extract_url_from_code(code_double), "https://example.com/bar")
        self.assertEqual(
            extract_url_from_code(code_backtick), "https://example.com/baz"
        )
        self.assertIsNone(extract_url_from_code(code_none))

    def test_coercion_failure_type(self):
        decision = HealingDecision(
            test_file="dummy.ts",
            failure_type="LOCATOR_DRIFT",
            failure_summary="A selector drifted",
            evidence=Evidence(error_log=""),
            hypothesis="",
            confidence_score=1.0,
            reasoning_steps=[],
            action_taken=HealingAction(original_code="", fixed_code="", description=""),
        )
        # Valid string should be coerced to the FailureType enum
        self.assertEqual(decision.failure_type, FailureType.LOCATOR_DRIFT)
        self.assertIsInstance(decision.failure_type, FailureType)

        # to_markdown should render the enum value correctly
        md = decision.to_markdown()
        self.assertIn("LOCATOR_DRIFT", md)

        # Phase 1 behaviour change: Pydantic raises ValidationError for unrecognised
        # failure types instead of silently coercing to UNKNOWN.  Invalid LLM output
        # is caught earlier by parse_llm_response(HealingAnalysis) before it reaches
        # HealingDecision, so silent coercion is no longer needed or desirable.
        from pydantic import ValidationError

        with self.assertRaises(ValidationError):
            HealingDecision(
                test_file="dummy.ts",
                failure_type="INVALID_TYPE_BLAH",
                failure_summary="Something failed",
                evidence=Evidence(error_log=""),
                hypothesis="",
                confidence_score=1.0,
                reasoning_steps=[],
                action_taken=HealingAction(
                    original_code="", fixed_code="", description=""
                ),
            )


if __name__ == "__main__":
    unittest.main()
