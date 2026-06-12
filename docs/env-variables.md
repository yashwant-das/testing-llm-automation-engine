# Environment Variables

This document describes all environment variables used by the AI Engineering Workbench.

## Quick Start

Copy `.env.example` to `.env` and choose **one** provider — only one is active at a time.

```bash
cp .env.example .env
```

Then edit `.env` to set `LLM_PROVIDER` and fill in the model names for your chosen provider.

---

## `.env` Template

```env
# ── Active provider ────────────────────────────────────────────────────────────
# Set LLM_PROVIDER to either "lm_studio" or "ollama" — only one is active.
LLM_PROVIDER=lm_studio

# ── LM Studio (active when LLM_PROVIDER=lm_studio) ────────────────────────────
LM_STUDIO_URL=http://localhost:1234/v1
LM_STUDIO_TEXT_MODEL=qwen/qwen3.6-35b-a3b    # text / code model
LM_STUDIO_VISION_MODEL=google/gemma-4-26b-a4b # multimodal model

# ── Ollama (active when LLM_PROVIDER=ollama) ───────────────────────────────────
# To switch: change LLM_PROVIDER=ollama above and uncomment the lines below.
# OLLAMA_URL=http://localhost:11434/v1
# OLLAMA_TEXT_MODEL=qwen3.6:latest
# OLLAMA_VISION_MODEL=gemma4:26b

# ── Optional ───────────────────────────────────────────────────────────────────
# LOG_LEVEL=INFO    # DEBUG | INFO | WARNING | ERROR
```

---

## How to switch providers

To use Ollama instead of LM Studio, make two edits to `.env`:

1. Change `LLM_PROVIDER=lm_studio` → `LLM_PROVIDER=ollama`
2. Uncomment the `OLLAMA_*` lines and fill in your model names

The `.env` file is loaded automatically at startup via `python-dotenv`. No restart of LM Studio or Ollama is needed — just restart `src/app.py`.

---

## Variable Reference

### `LLM_PROVIDER`

| | |
| --- | --- |
| **Type** | String |
| **Default** | `lm_studio` |
| **Options** | `lm_studio`, `ollama` |

Selects the active LLM backend. Only variables for the selected provider are used; the other set is ignored.

---

### LM Studio variables

#### `LM_STUDIO_URL`

| | |
| --- | --- |
| **Type** | String (URL) |
| **Default** | `http://localhost:1234/v1` |

Base URL of the LM Studio local server.

#### `LM_STUDIO_TEXT_MODEL`

| | |
| --- | --- |
| **Type** | String |
| **Default** | `qwen/qwen3.6-35b-a3b` |

Name of the text/code model loaded in LM Studio. Used by the Generation and Healing pipelines.

#### `LM_STUDIO_VISION_MODEL`

| | |
| --- | --- |
| **Type** | String |
| **Default** | `google/gemma-4-26b-a4b` |

Name of the vision (multimodal) model loaded in LM Studio. Used by the Vision pipeline.

#### `LM_STUDIO_API_KEY`

| | |
| --- | --- |
| **Type** | String |
| **Default** | `lm-studio` |

Placeholder API key. LM Studio accepts any non-empty string.

---

### Ollama variables

#### `OLLAMA_URL`

| | |
| --- | --- |
| **Type** | String (URL) |
| **Default** | `http://localhost:11434/v1` |

Base URL of the Ollama local server.

#### `OLLAMA_TEXT_MODEL`

| | |
| --- | --- |
| **Type** | String |
| **Default** | `qwen3.6:latest` |

Name of the text/code model pulled in Ollama. Used by the Generation and Healing pipelines.

#### `OLLAMA_VISION_MODEL`

| | |
| --- | --- |
| **Type** | String |
| **Default** | `gemma4:26b` |

Name of the vision model pulled in Ollama. Used by the Vision pipeline.

---

### Optional variables

#### `LOG_LEVEL`

| | |
| --- | --- |
| **Type** | String |
| **Default** | `INFO` |
| **Options** | `DEBUG`, `INFO`, `WARNING`, `ERROR` |

Controls the verbosity of framework log output. Set to `DEBUG` for full LLM prompt/response traces. Third-party loggers (`httpx`, `openai._base_client`, `gradio`) are always suppressed below `WARNING` regardless of this setting.
