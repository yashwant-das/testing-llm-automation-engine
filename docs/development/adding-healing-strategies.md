# Adding a New Healing Strategy

> How to add a new `RepairStrategy` value and the corresponding AST transformation.

---

## Architecture of the Repair Pipeline

The repair pipeline has two layers:

1. **`schemas/healing.py`** — `RepairStrategy` enum declares what strategy names are valid. The LLM chooses one when it builds a `HealingDecision`.
2. **`scripts/ast_repair.js`** — Node.js/ts-morph script that receives `{ strategy, source, original_code, fixed_code }` via stdin and returns `{ success, source, nodes_matched }`. Each `case` in the `switch(strategy)` block implements one strategy.
3. **`src/healing/repair.py`** — Python dispatcher. Calls `ast_repair.js` for any strategy that is not `STRING_REPLACE`. Falls back to string replacement if AST gives 0 nodes matched, and to unchanged code if string replacement also cannot find the target.

The LLM does not call `ast_repair.js` directly. It writes a `HealingDecision` containing `repair_strategy`, `original_code`, and `fixed_code`. `repair.py` calls `ast_repair.js` with those values.

---

## Existing Strategies

| Strategy           | `repair_strategy` value | What the AST does                                                                                                                                                                    |
| ------------------ | ----------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| `STRING_REPLACE`   | `"string_replace"`      | Python-only; no AST script call. Exact or line-normalised string substitution.                                                                                                       |
| `SELECTOR_REPLACE` | `"selector_replace"`    | Replaces the first string argument in `locator()`, `getByRole()`, `getByLabel()`, `getByText()`, `getByPlaceholder()` calls project-wide where the argument matches `original_code`. |
| `IMPORT_ADD`       | `"import_add"`          | Parses `fixed_code` as an import statement and inserts it at the top of the file. Skips if a matching import already exists.                                                         |
| `TIMEOUT_ADJUST`   | `"timeout_adjust"`      | Finds `{ timeout: N }` property values in the file and replaces any that match the numeric value in `original_code`.                                                                 |
| `ROLE_ARGUMENT`    | `"role_argument"`       | Finds `getByRole(role, { name: '...' })` calls where `name` matches `original_code` and replaces the name option value.                                                              |
| `ASSERTION_SWAP`   | `"assertion_swap"`      | Renames an assertion method in `expect(...).<method>()` chains where the method name matches `original_code`.                                                                        |

---

## Step 1: Add the Enum Value

In `schemas/healing.py`:

```python
class RepairStrategy(str, Enum):
    STRING_REPLACE   = "string_replace"
    SELECTOR_REPLACE = "selector_replace"
    IMPORT_ADD       = "import_add"
    TIMEOUT_ADJUST   = "timeout_adjust"
    ROLE_ARGUMENT    = "role_argument"
    ASSERTION_SWAP   = "assertion_swap"
    WAIT_FOR_UPDATE  = "wait_for_update"   # <-- new
```

Also update the JSON example in the prompt contract comment in `schemas/healing.py`:

```python
"repair_strategy": "string_replace | selector_replace | import_add | timeout_adjust | role_argument | assertion_swap | wait_for_update",
```

---

## Step 2: Implement the AST Transformation

In `scripts/ast_repair.js`, add a new function and a new `case`:

```javascript
/**
 * wait_for_update: Replace waitForSelector() calls whose argument matches
 * original_code with waitForSelector(fixed_code, { state: 'visible' }).
 *
 * @param {SourceFile} sourceFile  - ts-morph SourceFile
 * @param {string} originalCode   - Selector string to find
 * @param {string} fixedCode      - Replacement selector string
 * @returns {{ success: boolean, nodesMatched: number }}
 */
function waitForUpdate(sourceFile, originalCode, fixedCode) {
  let nodesMatched = 0;
  sourceFile.getDescendantsOfKind(SyntaxKind.CallExpression).forEach((call) => {
    const expr = call.getExpression();
    if (!expr || !expr.getText().endsWith('waitForSelector')) return;
    const args = call.getArguments();
    if (args.length === 0) return;
    const first = args[0];
    if (first.getKind() !== SyntaxKind.StringLiteral) return;
    const val = first.getLiteralText();
    if (val !== originalCode) return;

    // Replace the first argument with fixedCode
    first.replaceWithText(JSON.stringify(fixedCode));
    nodesMatched++;
  });
  return { success: nodesMatched > 0, nodesMatched };
}
```

Then add the case to the `switch` statement (around line 388):

```javascript
case 'wait_for_update':
    result = waitForUpdate(sourceFile, original_code, fixed_code);
    break;
```

---

## Step 3: Tell the Healer Prompt About the New Strategy

In `prompts/healer.md`, update the `repair_strategy` description. It currently lists the 6 valid values — add the new one:

```markdown
- `wait_for_update`: replace a `waitForSelector()` call with a different selector
```

Increment the `version` in `prompts/manifest.json`:

```json
{
  "healer": {
    "version": "2"
  }
}
```

---

## Step 4: Write Tests

In `tests/unit_test_fixer.py` or `tests/unit_test_ast_repair.py`, add tests for the new strategy:

```python
class TestWaitForUpdateStrategy(unittest.TestCase):
    def test_replaces_selector_in_wait_for_selector(self):
        code = """
import { test } from "@playwright/test";
test("t", async ({ page }) => {
    await page.waitForSelector(".old-selector");
});
"""
        decision = make_decision(
            repair_strategy="wait_for_update",
            original_code=".old-selector",
            fixed_code=".new-selector",
        )
        result = apply_fix(Path("test.spec.ts"), code, decision)
        self.assertIn(".new-selector", result)
        self.assertNotIn(".old-selector", result)

    def test_no_match_falls_back_to_string(self):
        code = """await page.waitForSelector(".unrelated");"""
        decision = make_decision(
            repair_strategy="wait_for_update",
            original_code=".does-not-exist",
            fixed_code=".new-selector",
        )
        # AST finds 0 nodes → falls back to string replacement → also 0 matches → unchanged
        result = apply_fix(Path("test.spec.ts"), code, decision)
        self.assertEqual(result, code)
```

---

## Step 5: Add a Benchmark Case

Add a case to `benchmarks/healing/fixtures/repair_scenarios.json` that exercises the new strategy:

```json
{
  "id": "heal-006",
  "description": "waitForSelector with stale selector — should switch to getByRole",
  "broken_test_file": "tests/fixtures/broken_wait.spec.ts",
  "injected_failure_type": "LOCATOR_DRIFT",
  "error_log": "Error: waitForSelector: No element matches selector '.old-btn'",
  "checks": {
    "expected_failure_type": "LOCATOR_DRIFT",
    "must_fix_pattern": ".old-btn",
    "fixed_code_must_contain": [".new-btn"],
    "code_must_change": true
  }
}
```

---

## Key Rules

- The LLM selects the `repair_strategy` — it should be the most precise strategy for the fix, not `string_replace` as a default. `string_replace` is the fallback the runtime uses, not the strategy the LLM should prefer.
- `ast_repair.js` must handle the case where `original_code` has 0 matches without throwing — return `{ success: false, nodesMatched: 0 }` and `repair.py` falls back automatically.
- Do not add strategies that require side effects (network, file system reads beyond the in-memory source). `ast_repair.js` receives source code in stdin and must return modified source in stdout.
- Every new strategy must have a test in `unit_test_ast_repair.py` (needs Node.js) or `unit_test_fixer.py` (string fallback only). CI runs both.
