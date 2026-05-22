import unittest

from src.agents.healer import apply_fix
from src.models.healing_model import (
    Evidence,
    FailureType,
    HealingAction,
    HealingDecision,
)


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


if __name__ == "__main__":
    unittest.main()
