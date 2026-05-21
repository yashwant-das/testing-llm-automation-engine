# Environment Variables

This document describes all environment variables used by the Testing LLM Repair Engine.

## Configuration

Create a `.env` file in the project root with the following variables:

```bash
# LM Studio Configuration
# URL where LM Studio is running (default: http://localhost:1234/v1)
LM_STUDIO_URL=http://localhost:1234/v1

# API Key for LM Studio (default: lm-studio)
LM_STUDIO_API_KEY=lm-studio

# Default model name for text generation (default: local-model)
DEFAULT_MODEL=local-model

# Vision model name for image analysis (default: local-model)
VISION_MODEL=local-model
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
- **Default**: `qwen3-coder:latest`
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
OLLAMA_MODEL=qwen3-coder:latest
OLLAMA_VISION_MODEL=qwen3-vl:30b
```
