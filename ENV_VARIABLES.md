# Environment Variables

This document describes all environment variables used by the Testing LLM Automation Engine.

## Configuration

Create a `.env` file in the project root with the following variables:

```bash
# LM Studio Configuration
# URL where LM Studio is running (default: http://localhost:1234/v1)
LM_STUDIO_URL=http://localhost:1234/v1

# API Key for LM Studio (default: lm-studio)
LM_STUDIO_API_KEY=lm-studio

# Text/code model name for LM Studio
LM_STUDIO_MODEL=qwen/qwen3-coder-30b

# Vision model name for LM Studio
LM_STUDIO_VISION_MODEL=qwen/qwen3-vl-30b

# Optional Ollama-compatible configuration
LLM_PROVIDER=lm_studio
OLLAMA_URL=http://localhost:11434/v1
OLLAMA_MODEL=gemma4:26b
OLLAMA_VISION_MODEL=qwen3-vl:30b
```

## Variable Descriptions

### `LLM_PROVIDER`

- **Type**: String
- **Default**: `lm_studio`
- **Options**: `lm_studio`, `ollama`
- **Description**: Determines which LLM service to connect to.

### `LM_STUDIO_URL`

- **Type**: String (URL)
- **Default**: `http://localhost:1234/v1`
- **Description**: The base URL when `LLM_PROVIDER` is set to `lm_studio`.

### `LM_STUDIO_API_KEY`

- **Type**: String
- **Default**: `lm-studio`
- **Description**: API key for LM Studio.

### `OLLAMA_URL`

- **Type**: String (URL)
- **Default**: `http://localhost:11434/v1`
- **Description**: The base URL when `LLM_PROVIDER` is set to `ollama`.

### `LM_STUDIO_MODEL`

- **Type**: String
- **Default**: `qwen/qwen3-coder-30b`
- **Description**: Text generation model name for LM Studio.

### `LM_STUDIO_VISION_MODEL`

- **Type**: String
- **Default**: `qwen/qwen3-vl-30b`
- **Description**: Vision model name for LM Studio.

### `OLLAMA_MODEL`

- **Type**: String
- **Default**: `gemma4:26b`
- **Description**: Text generation model name for Ollama.

### `OLLAMA_VISION_MODEL`

- **Type**: String
- **Default**: `qwen3-vl:30b`
- **Description**: Vision model name for Ollama.

## Usage

The application uses `python-dotenv` to load these variables from a `.env` file. If no `.env` file exists, the defaults
listed above will be used.

## Example `.env` File

```bash
LM_STUDIO_API_KEY=lm-studio
LLM_PROVIDER=lm_studio
OLLAMA_URL=http://localhost:11434/v1
LM_STUDIO_MODEL=qwen/qwen3-coder-30b
LM_STUDIO_VISION_MODEL=qwen/qwen3-vl-30b
OLLAMA_MODEL=gemma4:26b
OLLAMA_VISION_MODEL=qwen3-vl:30b
```
