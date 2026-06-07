# Documentation

This folder contains all project documentation. Start here.

---

## Reading paths

Choose the path that matches your goal.

### "I want to understand what this project is and why it exists"

1. [`/README.md`](../README.md) — what the project does, quick start, repo structure
1. [`ai-systems-engineering.md`](ai-systems-engineering.md) — the engineering philosophy: why structured outputs, evaluation, observability, and AST repair matter in AI pipelines
1. [`architecture/overview.md`](architecture/overview.md) — how the six subsystems fit together

### "I want to understand how it works technically"

After the overview above, go deeper by subsystem:

1. [`architecture/healing.md`](architecture/healing.md) — the core pipeline (classifier → planner → repair → verify)
1. [`architecture/llm-layer.md`](architecture/llm-layer.md) — LLM routing, retry policy, provider abstraction
1. [`architecture/context-collection.md`](architecture/context-collection.md) — how browser context is gathered in a single Playwright session
1. [`architecture/generation.md`](architecture/generation.md) — DOM-based test generation flow
1. [`architecture/observability.md`](architecture/observability.md) — JSONL tracing, span schema, Trace Inspector
1. [`architecture/evaluation.md`](architecture/evaluation.md) — evaluation framework design

### "I want to understand why decisions were made"

1. [`decisions.md`](decisions.md) — all Architecture Decision Records (ADR-001 through ADR-011), each covering context, decision, alternatives considered, and consequences

### "I want to understand the current UX state and what needs to change"

1. [`history/phase-16-ui-audit.md`](history/phase-16-ui-audit.md) — Phase 16 audit of the workbench UI against the post-modernization architecture: strengths, UX debt, visibility/workflow gaps, and prioritized recommendations

### "I want to set it up and run it"

1. [`development/setup.md`](development/setup.md) — prerequisites, install, first run
1. [`env-variables.md`](env-variables.md) — all environment variables with defaults and descriptions
1. [`docker.md`](docker.md) — running with Docker Compose

### "I want to contribute or extend it"

1. [`development/testing.md`](development/testing.md) — how to write and run tests
1. [`development/debugging.md`](development/debugging.md) — diagnosing the five common failure modes
1. [`development/adding-models.md`](development/adding-models.md) — adding a new LLM provider
1. [`development/adding-healing-strategies.md`](development/adding-healing-strategies.md) — adding a new repair strategy end-to-end
1. [`development/adding-benchmarks.md`](development/adding-benchmarks.md) — extending the benchmark suite
1. [`AGENTS.md`](../AGENTS.md) — for AI assistants: module map, where to add code, command reference

### "I want to understand the evaluation and benchmark methodology"

1. [`evaluation/benchmarks.md`](evaluation/benchmarks.md) — what benchmarks exist and what they measure
1. [`evaluation/datasets.md`](evaluation/datasets.md) — dataset format, mutation engine, versioning
1. [`evaluation/scoring.md`](evaluation/scoring.md) — how scores are computed
1. [`evaluation/reproducibility.md`](evaluation/reproducibility.md) — what makes a run reproducible
1. [`evaluation/model-comparison.md`](evaluation/model-comparison.md) — how to compare models

### "I want to understand how prompts are managed"

1. [`prompts/overview.md`](prompts/overview.md) — prompt management philosophy, versioning approach
1. [`prompts/healing.md`](prompts/healing.md) — healer prompt design and structure
1. [`prompts/generation.md`](prompts/generation.md) — generator prompt design
1. [`prompts/versioning.md`](prompts/versioning.md) — how prompt versions are tracked and hashed

---

## Folder map

```text
docs/
├── README.md                  ← you are here
│
├── ai-systems-engineering.md  ← conceptual guide: patterns behind the project
├── decisions.md               ← ADRs: why things are the way they are
├── governance.md              ← rules for keeping docs accurate
├── scorecard.md               ← repository maturity scores over time
│   ├── phase-16-ui-audit.md   ← Phase 16 audit of the workbench UX
├── backlog.md                 ← unscheduled future work and experiments
│
├── env-variables.md           ← reference: all environment variables
├── docker.md                  ← reference: Docker setup and deployment
│
├── architecture/              ← how each subsystem is designed
│   ├── overview.md            ← start here for technical understanding
│   ├── healing.md
│   ├── generation.md
│   ├── llm-layer.md
│   ├── context-collection.md
│   ├── observability.md
│   └── evaluation.md
│
├── development/               ← contributor and developer guides
│   ├── setup.md               ← start here for local development
│   ├── testing.md
│   ├── debugging.md
│   ├── adding-models.md
│   ├── adding-healing-strategies.md
│   └── adding-benchmarks.md
│
├── evaluation/                ← benchmark and evaluation methodology
│   ├── benchmarks.md
│   ├── datasets.md
│   ├── scoring.md
│   ├── reproducibility.md
│   └── model-comparison.md
│
├── prompts/                   ← prompt engineering documentation
│   ├── overview.md
│   ├── healing.md
│   ├── generation.md
│   └── versioning.md
│
└── history/                   ← archived: completed plans, past evaluations
    └── README.md              ← explains what is archived and why
```

---

## What does not belong in docs/

- Source code comments and inline documentation → live in `src/`
- Prompt text → lives in `prompts/` at the project root
- Test fixtures → live in `tests/fixtures/`
- Runtime artifacts (traces, healing decisions) → live in `logs/` and `tests/artifacts/`
