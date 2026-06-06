# AST Tool Evaluation for TypeScript Test Repair

> Evaluation for Phase 5 — AST-Based Repair
> Date: 2026-06-06
> Decision: ts-morph (see ADR-003)

---

## Problem Statement

`src/healing/repair.py:apply_fix()` currently repairs Playwright tests using
two string strategies:

1. **Exact string replacement** — replaces the first occurrence of `original_code`
   in the file when the indentation levels match.
2. **Normalized sliding-window match** — strips leading whitespace from each line
   before comparing, then re-indents the replacement to match the matched block.

Both strategies fail on **structural repairs**:

- A selector that appears in three places → only the first is fixed
- A missing import → cannot be added without touching a non-contiguous location
- A timeout value buried inside an options object → only found if the exact text matches
- An assertion method rename → may miss cases if surrounded by different whitespace

---

## Candidates Evaluated

### ts-morph

**What it is:** A high-level TypeScript AST manipulation library built on top of
the official TypeScript compiler (`typescript` package). Exposes the full
TypeScript AST with read/write APIs.

**TypeScript support:** Native — built on the TypeScript compiler. Understands
generics, decorators, type assertions, template literals, and all TypeScript
syntax.

**AST modification:** Full read-write. Supports node replacement, insertion,
deletion, and transformation. Changes preserve surrounding whitespace and
comments (formatting-preserving).

**Python interoperability:** Via Node.js subprocess. Python sends a JSON repair
spec on stdin; the Node.js script applies the transformation and returns the
modified source on stdout.

**Dependencies:** Requires `ts-morph` npm package + `typescript` (already
installed). Node.js is already required by the project (Playwright uses it).

**API quality:** Stable; v24+ with excellent documentation and examples. The
compiler API is documented and the high-level ts-morph wrapper handles the
ceremony.

**Maintenance burden:** Low. ts-morph tracks the TypeScript compiler closely.
TypeScript is a Playwright dependency so it will always be present.

**Learning value:** High. The TypeScript compiler API is the canonical way to
build TypeScript tooling; understanding it is directly applicable to future
work.

**Verdict:** ✅ Best choice.

---

### Babel

**What it is:** A JavaScript transpiler with an AST plugin system. TypeScript
support via `@babel/plugin-transform-typescript`.

**TypeScript support:** Partial. Babel strips TypeScript types for transpilation
but does not type-check. The AST representation differs from the TypeScript
compiler's.

**AST modification:** Via `@babel/traverse` and `@babel/types`. Supports node
replacement and insertion.

**Python interoperability:** Same subprocess pattern as ts-morph.

**Concerns:**

- TypeScript plugin drops type information — cannot use type-aware queries
- Decorator handling differs between Babel and TypeScript compiler
- Adds `@babel/core`, `@babel/traverse`, `@babel/types` as dependencies on top
  of the TypeScript packages already installed

**Verdict:** ❌ Rejected. TypeScript compiler support is second-class; adds
unnecessary dependencies when ts-morph uses the compiler we already have.

---

### tree-sitter

**What it is:** A parser generator that produces concrete syntax trees. Has a
Python library (`tree-sitter`) and a TypeScript grammar
(`tree-sitter-typescript`).

**TypeScript support:** Full parse support; grammar covers all TypeScript syntax.

**AST modification:** ❌ Read-only. tree-sitter is designed for query and
syntax highlighting, not mutation. Edits are done by manually splicing the
source string at byte offsets returned by the tree. This is more fragile than
ts-morph's node replacement API.

**Python interoperability:** Native Python bindings — no subprocess needed.

**Concerns:**

- No mutation API — string-based edits defeat the purpose of using an AST tool
- Python bindings require building native extensions; more fragile in CI

**Verdict:** ❌ Rejected. Read-only focus means we would still be doing string
surgery, just with more precise byte offsets.

---

### SWC

**What it is:** A Rust-based TypeScript/JavaScript compiler designed for speed
(used by Next.js, Vite, etc.).

**TypeScript support:** Full; designed as a TypeScript/JavaScript compiler.

**AST modification:** The `@swc/core` package exposes `transform()` with visitor
plugins, but the plugin API is experimental and requires Rust for non-trivial
transformations. JavaScript plugins via `@swc/core` are limited.

**Python interoperability:** Via subprocess or Node.js bindings.

**Concerns:**

- Plugin API is experimental and primarily Rust-based
- Not designed for ad-hoc programmatic AST mutation
- Primary use case is compilation/bundling, not repair tooling

**Verdict:** ❌ Rejected. Not designed for programmatic mutation; the plugin
system requires Rust for anything non-trivial.

---

## Decision

**Use ts-morph** via Node.js subprocess with a typed JSON protocol.

See ADR-003 for the formal decision record.

---

## Protocol Design

Python calls `node scripts/ast_repair.js` and communicates via JSON stdio:

**Input (stdin):**

```json
{
    "strategy": "selector_replace",
    "source": "... full TypeScript file content ...",
    "original_code": "page.locator('#old-btn').click()",
    "fixed_code": "page.locator('[data-testid=\"submit\"]').click()"
}
```

**Output (stdout):**

```json
{
    "success": true,
    "source": "... modified TypeScript file content ...",
    "changes": 1
}
```

On any unhandled error:

```json
{
    "success": false,
    "source": "... original source unchanged ...",
    "error": "description of what went wrong",
    "changes": 0
}
```

Python checks `success` and `changes > 0`. If either is false, it falls back
to the existing string replacement strategy (logged as a warning).

---

## Supported Repair Strategies (MVP)

| Strategy | Description | AST operation |
| --- | --- | --- |
| `selector_replace` | Replace a locator selector across the file | Find all matching string literals inside `locator()`/`getByX()` calls |
| `import_add` | Add a missing import statement | Insert import declaration at top; skip if module already imported |
| `timeout_adjust` | Change a timeout value | Find `{ timeout: N }` property assignments and update |
| `role_argument` | Correct a `getByRole` name option | Find `getByRole(role, { name: '...' })` and update name |
| `assertion_swap` | Change assertion method | Rename `.toBe()` → `.toEqual()` etc. in expect chains |
| `string_replace` | Existing fallback | Used when strategy is unknown or AST repair produced no changes |

---

## Fallback Behaviour

The string replacement strategy from Phase 4 is retained as a fallback:

1. If `repair_strategy` is `string_replace` → use string path directly (no Node.js call)
2. If AST repair returns `changes: 0` → fall back to string, log warning
3. If Node.js subprocess fails (timeout, FileNotFoundError, bad JSON) → fall back to string, log warning
4. If string replacement also produces no change → return unchanged code, log warning

This guarantees no regression: the existing tests continue to pass, and the
AST path is additive.
