# Healer Prompt

> Documents `prompts/healer.md` — version 2

---

## Purpose

The healer prompt instructs the LLM to diagnose a failing Playwright test and propose a specific code fix. It receives the heuristic pre-diagnosis, the broken test code, the error log, and all available page context.

---

## Inputs

The healer prompt is a system prompt. The calling code (`src/healing/planner.py`) injects three values at runtime:

| Placeholder      | Value                   | Example                          |
| ---------------- | ----------------------- | -------------------------------- |
| `{failure_type}` | Heuristic diagnosis     | `"TIMEOUT"`                      |
| `{confidence}`   | Heuristic confidence    | `"1.00"`                         |
| `{reason}`       | Heuristic reason string | `"TimeoutError pattern matched"` |

The user message contains:

- `FILE:` — the test file path
- `BROKEN CODE:` — the full TypeScript source
- `ERROR LOGS:` — first 2000 characters of the error log
- `PAGE DOM CONTEXT:` — cleaned HTML (if available, up to 30,000 chars)
- `ACCESSIBILITY TREE:` — ARIA snapshot (if available, up to 5,000 chars)
- `AVAILABLE LOCATORS:` — pre-extracted `getByRole()` strings (if available, up to 20)
- `BROWSER CONSOLE ERRORS:` — console errors (if available, up to 5)
- `FAILED NETWORK REQUESTS:` — network failures (if available, up to 5)

---

## Required Output

The LLM must return a valid JSON object matching `HealingAnalysis`:

```json
{
  "failure_type": "LOCATOR_DRIFT | TIMEOUT | ASSERTION_FAILED | ENVIRONMENT_ISSUE | POTENTIAL_APP_DEFECT",
  "failure_summary": "Short description of failure",
  "hypothesis": "Why the fix will work",
  "confidence_score": 0.95,
  "confidence_rationale": "One sentence explaining why this confidence level was chosen",
  "reasoning_steps": ["step 1", "step 2"],
  "root_cause_evidence": ["specific log line or DOM element that proves the diagnosis"],
  "action_taken": {
    "original_code": "EXACT contiguous block of code to replace (must match file exactly)",
    "fixed_code": "New contiguous block of code to insert",
    "description": "What changed",
    "repair_strategy": "string_replace | selector_replace | import_add | timeout_adjust | role_argument | assertion_swap"
  }
}
```

The schema is validated by `parse_llm_response(raw_content, HealingAnalysis)`. If any field fails validation, a `ValidationError` is raised and the planner returns a fallback `HealingDecision`.

---

## Repair Strategy Guide

The prompt includes a repair strategy selection guide that instructs the LLM to choose the most specific strategy:

| Strategy           | When to use                        | `original_code`         | `fixed_code`            |
| ------------------ | ---------------------------------- | ----------------------- | ----------------------- |
| `selector_replace` | A locator selector changed         | Old locator call        | New locator call        |
| `import_add`       | A required import is missing       | `""`                    | Full import statement   |
| `timeout_adjust`   | A timeout value needs to change    | Object with old timeout | Object with new timeout |
| `role_argument`    | A getByRole name option is wrong   | Old getByRole call      | New getByRole call      |
| `assertion_swap`   | An assertion method needs renaming | Old assertion call      | New assertion call      |
| `string_replace`   | Catch-all (none of the above)      | Old code block          | New code block          |

The repair strategy selection matters because it determines which AST transformation `scripts/ast_repair.js` will apply. Choosing `selector_replace` triggers file-wide selector replacement; choosing `string_replace` falls back to the sliding-window string matcher.

---

## Design Notes

**Heuristic pre-diagnosis is injected.** The system prompt tells the LLM: "The system has preliminarily analyzed the logs — your job is to verify this diagnosis (or correct it if you see strong evidence otherwise)." This anchors the LLM's reasoning and reduces hallucination for clear-cut cases.

**`original_code` must be a contiguous block.** The repair module requires the original code to be a single unbroken excerpt from the file. The prompt explicitly warns: "Do NOT skip lines between edits." If multiple non-adjacent parts need changing, include the unchanged lines between them in both blocks.

**Phase 9 fields are required.** `confidence_rationale` and `root_cause_evidence` were added in Phase 9 (prompt version 2). These allow the artifact to explain why the model was confident and what specific evidence it used.

---

## Version History

| Version | Change                                                                                             |
| ------- | -------------------------------------------------------------------------------------------------- |
| 1       | Initial healer prompt with basic diagnosis + code fix                                              |
| 2       | Added `repair_strategy` field (Phase 5) + `confidence_rationale` + `root_cause_evidence` (Phase 9) |
