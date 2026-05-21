# Repository Guidelines

## Project Structure & Module Organization

- `src/` holds the core agents, models, and utilities behind the QA pipeline (generator, healer, vision logic plus Playwright/browser helpers and prompt loaders).
- High-level orchestration (Gradio UI, CLI hooks) lives in `src/app.py`; any new feature should plug into the existing `agents/`, `models/`, or `utils/` packages, keeping helper modules focused per responsibility.
- External assets: `prompts/` stores system prompts, `docs/` deep-dives (architecture, demos, scenarios), and `tests/` contains `unit_test_*.py`, generated specs, artifacts, and vision screenshots that the agents consume.
- Playwright reports and execution artifacts are captured under `playwright-report/` and `test-results/`, so keep generated files out of version control (use `.gitignore` already configured).

## Build, Test, and Development Commands

- `npm install` + `npx playwright install` provision the JS toolchain before running any tests.
- `npm run lint` (runs JS, Py, and Markdown linting) ensures ESLint/Prettier, Flake8, and Markdownlint agree before committing.
- `npm run format` auto-formats JS via Prettier and Python via Black/Isort; run before lint or staging changes.
- `npm run test` executes the Playwright suite defined in `playwright.config.ts` and deposits reports under `playwright-report/`.
- `npm run test:unit` runs the Python `tests/unit_test_*.py` modules so heuristics and helpers stay covered.
- Docker: `docker build -t testingllmrepairengine .` followed by `docker run -p 7860:7860 --name testingllmrepairengine ...` mirrors production (see `DOCKER.md`).

## Coding Style & Naming Conventions

- JavaScript/TypeScript follows the Flat Config ESLint setup with 2-space indentation and Prettier formatting; run `npm run lint:js` or let Husky/lint-staged auto-fix staged files.
- Python code uses Black (88 char line, automatic string quoting) and Isort for imports; Flake8 guards for unused symbols.
- Markdown files should pass `markdownlint-cli2`; keep section headers consistent with sentence case (see README structure).
- Naming patterns: Python tests start with `unit_test_`, generated TypeScript specs land under `tests/generated/`, and healing artifacts are under `tests/artifacts/` for easy discovery.

## Testing Guidelines

- Playwright (`@playwright/test`) covers E2E flows invoked via `npm test`; store living failures in `test-results/`/`playwright-report/` for debugging.
- Python `unittest` modules verify deterministic heuristics; keep new logic in `tests/unit_test_*.py` and follow the existing `setUp`-style structure.
- Tests should target a single agent capability (generation, vision, healing) and assert both log output and artifact creation where applicable.
- Run `npm run lint` after tests to ensure linting passes; failing tests should be rerun with `DEBUG=1` to capture logs.

## Commit & Pull Request Guidelines

- Commits follow Conventional Commits (`feat:`, `fix:`, `chore:`) as seen in recent history; keep lines under 72 characters and the body focused on why.
- Pull requests must describe the change, list commands executed (lint/tests), link related issues or tickets, and attach a Playwright report or screenshot when UI behavior changes.
- Include before/after artifacts when healing logic shifts (e.g., new `HealingDecision` JSON) so reviewers can evaluate the fix trace.
- Tag reviewers early if the change touches docs, prompts, or prompts configuration to ensure cross-functional validation.

## Security & Configuration Tips

- Protect credentials by using ENV variables documented in `ENV_VARIABLES.md`; do not commit real keys.
- Prompt tweaks belong in `prompts/`; update both markdown and any JSON-loading helpers in tandem to keep LLM behavior predictable.
- When adding new agents, ensure their subprocess calls sanitize inputs and reuse the shared `validation.py` helpers.
