# Generator Prompt

> Documents `prompts/generator.md` — version 1

---

## Purpose

The generator prompt instructs the LLM to write a complete, runnable Playwright TypeScript test file from the provided page context and user scenario.

---

## Inputs

The generator prompt is a fixed system prompt — no runtime placeholders. The user message contains:

- Target URL
- Test scenario (plain English)
- Cleaned HTML (up to 30,000 chars from `context/dom.py`)
- Accessibility tree (up to 5,000 chars from `context/accessibility.py`)
- Locator candidates (up to 20 `getByRole()` strings from `context/locator_candidates.py`)
- Console errors (up to 5 from `context/console.py`)
- Failed network requests (up to 5 from `context/network.py`)

---

## Required Output

The LLM must return **only TypeScript code** — no markdown fences, no prose. The output is extracted via `_extract_code_block()` and validated into a `GenerationResult`.

The generated file must:

1. Start with `import { test, expect } from "@playwright/test";`
2. Include at least one `test()` block
3. Include at least one `expect()` assertion
4. Navigate to the target URL
5. Use selectors derived from the page context

---

## Selector Strategy

The prompt instructs the LLM to prefer selectors in this order:

1. `data-test` attributes (most stable)
2. `id` attributes (stable if not auto-generated)
3. ARIA roles from the accessibility tree (`getByRole`, `getByLabel`, `getByPlaceholder`)
4. Specific `class` selectors (last resort)

The locator candidates provided in the user message (pre-extracted from the a11y tree) are ready-to-use `getByRole()` strings. The LLM is instructed to prefer these when they match the intended element.

---

## Version History

| Version | Change                   |
| ------- | ------------------------ |
| 1       | Initial generator prompt |
