# Setup Guide

> Everything needed to run the project locally.

---

## Prerequisites

| Tool                | Version | Purpose                            |
| ------------------- | ------- | ---------------------------------- |
| Python              | 3.11+   | Pipeline and UI                    |
| Node.js             | 18+     | Playwright + AST repair (ts-morph) |
| `uv`                | any     | Python dependency management       |
| LM Studio or Ollama | any     | Local LLM inference                |

---

## Step 1: Clone and Install

```bash
git clone https://github.com/yashwant-das/testing-llm-automation-engine
cd testing-llm-automation-engine

# Python dependencies (creates .venv automatically)
uv sync

# Node.js dependencies + Playwright browsers
npm install
npx playwright install
```

---

## Step 2: Configure LLM

Copy `.env.example` to `.env` and activate **one** provider.

```bash
cp .env.example .env
```

### Using LM Studio

Edit `.env`:

```env
LLM_PROVIDER=lm_studio
LM_STUDIO_URL=http://localhost:1234/v1
LM_STUDIO_TEXT_MODEL=qwen/qwen3.6-35b-a3b
LM_STUDIO_VISION_MODEL=google/gemma-4-26b-a4b
```

Start LM Studio, load a text/code model and a vision model, then start the local server (default port 1234).

### Using Ollama

Edit `.env` — set the provider and uncomment the Ollama section:

```env
LLM_PROVIDER=ollama

# OLLAMA_URL=http://localhost:11434/v1      ← uncomment and fill in
# OLLAMA_TEXT_MODEL=qwen3.6:latest
# OLLAMA_VISION_MODEL=gemma4:26b
```

```bash
ollama pull qwen3.6:latest
ollama pull gemma4:26b
ollama serve
```

> **Only one provider is active at a time.** The `LLM_PROVIDER` value determines which set of variables is read. Variables for the inactive provider are ignored.

The `.env` file is loaded automatically at startup. No environment export or shell restart is needed.

---

## Step 3: Verify Setup

```bash
# Run unit tests (no LLM or browser required — should all pass)
uv run python -m pytest tests/unit_test_*.py -q
# Expected: 556 passed

# Run the classification benchmark (no LLM required)
uv run python -c "
from benchmarks.healing.runner import load_dataset, run_healing_benchmark
from schemas.evaluation import BenchmarkRunConfig
from pathlib import Path
config = BenchmarkRunConfig(
    model='heuristic', provider='local',
    prompt_name='n/a', prompt_version='1', prompt_hash='n/a',
    temperature=0.0, dataset_version='1.0.0', benchmark_type='healing-classification',
)
run = run_healing_benchmark(Path('benchmarks/healing/fixtures/repair_scenarios.json'), Path('.'), config)
print(f'{run.passed}/{run.total} passed')
"
# Expected: 4/4 passed

# Launch the workbench (requires LLM for generation/healing tabs)
uv run python src/app.py
# Open http://127.0.0.1:7860
```

---

## Troubleshooting

### "LLM connection refused" or "Connection error"

- Verify the active provider (`LLM_PROVIDER`) is actually running
- Check that the `*_URL` for the active provider matches the server address
- If the error says `model=qwen/qwen3.6-35b-a3b` but you configured a different model, the `.env` is not being picked up — ensure you ran `cp .env.example .env` and the file exists in the project root

### "npx playwright test: command not found"

```bash
npm install
npx playwright install
```

### "ModuleNotFoundError: No module named 'src'"

Run commands from the project root directory, not from inside `src/`.

### Unit tests fail with import errors

```bash
uv sync  # re-sync dependencies
```

### AST repair falls back to string replacement

Node.js is required for the AST repair path. Verify:

```bash
node --version   # must be 18+
node scripts/ast_repair.js  # should print usage, not an error
```

---

## Environment Variables Reference

| Variable                 | Active when | Default                     | Description                            |
| ------------------------ | ----------- | --------------------------- | -------------------------------------- |
| `LLM_PROVIDER`           | always      | `lm_studio`                 | `"lm_studio"` or `"ollama"`            |
| `LM_STUDIO_URL`          | lm_studio   | `http://localhost:1234/v1`  | LM Studio server URL                   |
| `LM_STUDIO_TEXT_MODEL`   | lm_studio   | `qwen/qwen3.6-35b-a3b`      | Text/code model name                   |
| `LM_STUDIO_VISION_MODEL` | lm_studio   | `google/gemma-4-26b-a4b`    | Vision model name                      |
| `LM_STUDIO_API_KEY`      | lm_studio   | `lm-studio`                 | Any non-empty string                   |
| `OLLAMA_URL`             | ollama      | `http://localhost:11434/v1` | Ollama server URL                      |
| `OLLAMA_TEXT_MODEL`      | ollama      | `qwen3.6:latest`            | Text/code model name                   |
| `OLLAMA_VISION_MODEL`    | ollama      | `gemma4:26b`                | Vision model name                      |
| `LOG_LEVEL`              | always      | `INFO`                      | `DEBUG` · `INFO` · `WARNING` · `ERROR` |

Full variable descriptions: [docs/env-variables.md](../env-variables.md)
