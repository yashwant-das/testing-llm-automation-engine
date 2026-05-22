# Healing Scenarios: Showcase of Intelligence

> This document details real-world scenarios where the **Healer Agent** demonstrates its reasoning capabilities.

---

## 1. The "Locator Drift" Scenario

**Scenario**: A developer changes an input or button selector used by a generated Playwright spec.

- **Heuristic Detection**: Playwright fails with a `TimeoutError`, strict-mode violation, or "locator resolved to 0 elements" message.
- **LLM Reasoning**: The agent reviews the failing code block, Playwright logs, and heuristic diagnosis to propose a specific contiguous patch.
- **The Fix**: It patches the test to use a more accurate selector, then re-runs the spec to verify the repair.

## 2. The "Dynamic Content" Scenario

**Scenario**: A test expects a success message "Saved Successfully!", but the app now returns "Changes saved!".

- **Heuristic Detection**: The test fails an assertion.
- **LLM Reasoning**: The agent reads the assertion log and failing assertion code, then determines whether the expected text should be updated.
- **The Fix**: It updates the `expect(...).toContainText()` call to match the new string.

## 3. The "Network Flakiness" Scenario

**Scenario**: A test fails because a 3rd party API returned a `500 Internal Server Error` during the run.

- **Heuristic Detection**: The agent uses Regex to find `500` in the Playwright logs.
- **Intelligence**: Instead of trying to "fix" the code, the agent correctly identifies this as a **POTENTIAL_APP_DEFECT** with **0.8 confidence**.
- **Operational Insight**: The agent records the likely infrastructure or application issue in the `HealingDecision` artifact instead of blindly treating every failure as locator drift.

## 4. The "Race Condition" Scenario

**Scenario**: A button is not ready when the test tries to interact with it.

- **Heuristic Detection**: `TimeoutError` while waiting for the element to be "visible and stable".
- **LLM Reasoning**: The agent uses the failing code and Playwright call log to infer whether the test needs a better wait or a more reliable locator.
- **The Fix**: It may insert a Playwright-native wait or assertion before the interaction, then verifies the changed spec.

---

### Try it Yourself

Purposefully break any generated script (change a locator, delete a character in a selector) and run it through the **Self-Healer** tab in the UI.
