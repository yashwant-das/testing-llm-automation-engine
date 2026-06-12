# Setup Guide

> Everything needed to run the project locally.

---

## Prerequisites

| Tool | Version | Purpose |
| --- | --- | --- |
| Python | 3.11+ | Pipeline and UI |
| Node.js | 18+ | Playwright + AST repair (ts-morph) |
| `uv` | any | Python dependency management |
| LM Studio or Ollama | any | Local LLM inference |

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

Create a `.env` file in the project root. The project reads environment variables via the `LLMClientFactory` at call time (no reload required after changes).

### LM Studio

```env
LLM_PROVIDER=lm_studio
LM_STUDIO_URL=http://localhost:1234/v1
LM_STUDIO_MODEL=qwen3-coder-30b
LM_STUDIO_VISION_MODEL=qwen2.5-vl-7b
LM_STUDIO_API_KEY=lm-studio
```

Start LM Studio, load a text/code model and a vision model, start the local server. The default port is 1234.

### Ollama

```env
LLM_PROVIDER=ollama
OLLAMA_URL=http://localhost:11434/v1
OLLAMA_MODEL=qwen3-coder:30b
OLLAMA_VISION_MODEL=llava:13b
OLLAMA_API_KEY=ollama
```

```bash
ollama pull qwen3-coder:30b
ollama pull llava:13b
ollama serve
```

---

## Step 3: Verify Setup

```bash
# Run unit tests (no LLM or browser required — should all pass)
uv run python -m pytest tests/unit_test_*.py -q
# Expected: 553 passed

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

### "LLM connection refused"

- Verify LM Studio or Ollama is running
- Check that `LM_STUDIO_URL` / `OLLAMA_URL` matches the server address
- Verify the model is loaded and the server is started in LM Studio

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

| Variable | Required | Default | Description |
| --- | --- | --- | --- |
| `LLM_PROVIDER` | Yes | — | `"lm_studio"` or `"ollama"` |
| `LM_STUDIO_URL` | If lm_studio | `http://localhost:1234/v1` | LM Studio server URL |
| `LM_STUDIO_MODEL` | If lm_studio | — | Text/code model name |
| `LM_STUDIO_VISION_MODEL` | If lm_studio | — | Vision model name |
| `LM_STUDIO_API_KEY` | No | `"lm-studio"` | Any non-empty string |
| `OLLAMA_URL` | If ollama | `http://localhost:11434/v1` | Ollama server URL |
| `OLLAMA_MODEL` | If ollama | `"gemma4:26b"` | Text/code model name |
| `OLLAMA_VISION_MODEL` | If ollama | — | Vision model name |
| `OLLAMA_API_KEY` | No | `"ollama"` | Any non-empty string |
