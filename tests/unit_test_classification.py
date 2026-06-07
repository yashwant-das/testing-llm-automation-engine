import unittest

from schemas.shared import FailureType
from src.healing.classifier import classify_failure_heuristic


class TestFailureClassification(unittest.TestCase):
    def test_timeout(self):
        logs = "TimeoutError: page.goto: Timeout 30000ms exceeded."
        f_type, conf, reason = classify_failure_heuristic(logs)
        self.assertEqual(f_type, FailureType.TIMEOUT)
        self.assertEqual(conf, 1.0)

    def test_waiting_for_selector(self):
        logs = "Error: waiting for selector '#foo' failed"
        f_type, conf, reason = classify_failure_heuristic(logs)
        self.assertEqual(f_type, FailureType.TIMEOUT)
        self.assertEqual(conf, 1.0)

    def test_assertion_fail(self):
        logs = "Error: expect(received).toBe(expected)\nExpected: 5\nReceived: 3"
        f_type, conf, reason = classify_failure_heuristic(logs)
        self.assertEqual(f_type, FailureType.ASSERTION_FAILED)
        self.assertEqual(conf, 1.0)

    def test_locator_drift(self):
        logs = "Error: strict mode violation: locator('button') resolved to 2 elements"
        f_type, conf, reason = classify_failure_heuristic(logs)
        self.assertEqual(f_type, FailureType.LOCATOR_DRIFT)
        self.assertEqual(conf, 0.9)

    def test_locator_drift_suggestion(self):
        logs = "locator resolved to 0 elements. Did you mean 'Submit Result'?"
        f_type, conf, reason = classify_failure_heuristic(logs)
        self.assertEqual(f_type, FailureType.LOCATOR_DRIFT)
        self.assertEqual(conf, 0.8)

    def test_missing_locator(self):
        logs = "locator resolved to 0 elements"
        f_type, conf, reason = classify_failure_heuristic(logs)
        self.assertEqual(f_type, FailureType.LOCATOR_NOT_FOUND)
        self.assertEqual(conf, 0.7)

    def test_target_closed(self):
        logs = "TargetClosedError: browser has been closed"
        f_type, conf, reason = classify_failure_heuristic(logs)
        self.assertEqual(f_type, FailureType.ENVIRONMENT_ISSUE)
        self.assertEqual(conf, 1.0)

    def test_waiting_for_locator_heuristic(self):
        logs = "Error: waiting for locator('button') to be visible"
        f_type, conf, reason = classify_failure_heuristic(logs)
        self.assertEqual(f_type, FailureType.TIMEOUT)
        self.assertEqual(conf, 1.0)


if __name__ == "__main__":
    unittest.main()
