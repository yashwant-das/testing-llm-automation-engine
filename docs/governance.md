# Documentation Governance

> Lightweight rules for keeping documentation accurate and maintainable.
> Prefer fewer documents over more. Prefer accuracy over preservation.

---

## Sources of Truth

| Question | Authoritative source |
| --- | --- |
| What is this project? | `README.md` |
| How do I set it up? | `docs/development/setup.md` |
| How does the architecture work? | `docs/architecture/` |
| Why was X decided? | `docs/decisions.md` (ADRs) |
| How do I add X? | `docs/development/adding-*.md` |
| How do I debug X? | `docs/development/debugging.md` |
| What are the environment variables? | `docs/env-variables.md` |
| How do I run in Docker? | `docs/docker.md` |
| What is the AI assistant expected to know? | `AGENTS.md` |
| What's the evaluation methodology? | `docs/evaluation/` |
| How are prompts managed? | `docs/prompts/` |
| What are the maturity scores? | `docs/scorecard.md` |
| What future work exists? | `docs/backlog.md` |
| What historical decisions were made? | `docs/history/` |

---

## Update Requirements

### When to update documentation

| Event | Required action |
| --- | --- |
| New module added to `src/` | Update `README.md` repo structure; update `AGENTS.md` module map |
| New environment variable | Update `docs/env-variables.md`; update `docs/development/setup.md` |
| New LLM provider supported | Update `docs/development/adding-models.md` and `docs/env-variables.md` |
| New repair strategy added | Update `docs/development/adding-healing-strategies.md` |
| Architecture boundary changes | Update relevant `docs/architecture/*.md` |
| Significant technical decision made | Add an ADR to `docs/decisions.md` |
| UI tab renamed or added | Update `README.md`, `AGENTS.md`, `docs/docker.md` |
| New benchmark added | Update `docs/evaluation/benchmarks.md` |
| Prompt file changed significantly | Update `docs/prompts/healing.md` or `generation.md`; bump version in `prompts/manifest.json` |
| Phase or milestone completed | Update `docs/scorecard.md` with new maturity scores |

### What does NOT require documentation updates

- Bug fixes that do not change module interfaces
- Performance improvements with no API changes
- Test additions
- Dependency version bumps

---

## Architecture Decision Records

Write an ADR in `docs/decisions.md` when:

- A tool or library is evaluated and selected (or rejected)
- A design pattern is adopted (e.g., why thread-local vs. asyncio)
- A module boundary is established or changed
- A decision is made that future contributors might question

Do not write an ADR for:

- Implementation details that are obvious from the code
- Decisions that can be reversed without architectural impact
- Minor configuration choices

ADR format: **Context → Decision → Alternatives → Consequences**

---

## Archive Policy

Documentation moves to `docs/history/` when:

- It describes a system or process that no longer exists
- It was a one-time planning or evaluation document whose conclusions are captured elsewhere
- It has no value for a new contributor who was not involved in its creation

Documentation is **deleted** (not archived) when:

- It is inaccurate and the accurate version exists elsewhere
- It is purely duplicative of another document

Active documentation is never deleted without first checking whether any other document links to it.

---

## Document Ownership

This is a single-engineer project. All documentation is owned by the project author.

For AI assistants working in this repository: `AGENTS.md` describes what you are expected
to know about the codebase structure and where to add new code.

---

## Anti-Patterns

These patterns have caused documentation drift in this project's past. Avoid them.

| Anti-pattern | Why it fails |
| --- | --- |
| Keeping "OPEN" items in technical debt after they are resolved | Creates false signal that problems still exist |
| Leaving `[ ]` checkboxes in completed plans | Misleads contributors about the project's state |
| Leaving "will be done in Phase N" comments in code after Phase N completes | Becomes noise that obscures real intent |
| Writing architecture docs before the implementation is stable | Requires rewriting the doc when the implementation changes |
| Creating evaluation docs without recording the decision in an ADR | Decision rationale gets lost when the evaluation doc is eventually archived |
| Keeping SaaS marketing language in a reference implementation project | Confuses contributors about the project's purpose |

---

## Validation

Before merging significant documentation changes:

1. Run `npm run lint:md` to verify Markdown syntax
2. Spot-check any file paths mentioned in the docs against the actual repository
3. Verify any commands mentioned work from the project root

For architecture docs: verify that the described module names and public APIs match the actual source files.
