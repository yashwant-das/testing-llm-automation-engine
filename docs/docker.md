# Docker Workflow Guide

This guide covers building and running the AI Engineering Workbench in Docker, including manual debugging and healing workflows.

## Prerequisites

- Docker installed and running
- **Either** LM Studio (Server ON, Port 1234) **OR** Ollama (Server ON, Port 11434) running
- A broken test file in `tests/generated/` (e.g., `my_broken_test.spec.ts`)

## Building the Docker Image

Build the Docker image with the following command:

```bash
docker build -t testing-llm-automation-engine .
```

This creates a Docker image named `testing-llm-automation-engine` using the `Dockerfile` in the project root.

## Running the Container

### Basic Run

Run the container with port mapping to access the Gradio UI:

```bash
docker run -p 7860:7860 \
  --name testing-llm-automation-engine \
  --add-host=host.docker.internal:host-gateway \
  -e LM_STUDIO_URL="http://host.docker.internal:1234/v1" \
  -e PYTHONUNBUFFERED=1 \
  testing-llm-automation-engine
```

Access the Gradio interface at `http://localhost:7860`.

> [!TIP]
> Use the **Healing Pipeline** tab in the UI for a visual experience of the healing pipeline described below.
>
> Also, if you want to preserve your execution logs and decision artifacts after the container stops, consider mounting the `logs/` and `tests/artifacts/` directories as well (e.g., `-v "$(pwd)/logs:/app/logs" -v "$(pwd)/tests/artifacts:/app/tests/artifacts"`).

### With Environment File

If you have a `.env` file, mount it:

```bash
docker run -p 7860:7860 \
  --name testing-llm-automation-engine \
  --add-host=host.docker.internal:host-gateway \
  --env-file .env \
  -e LM_STUDIO_URL="http://host.docker.internal:1234/v1" \
  -e PYTHONUNBUFFERED=1 \
  testing-llm-automation-engine
```

### With Volume Mount (For Development)

Mount the `tests/generated` directory to edit files on your host and see changes in the container:

```bash
docker run -p 7860:7860 \
  --name testing-llm-automation-engine \
  --add-host=host.docker.internal:host-gateway \
  --env-file .env \
  -e LM_STUDIO_URL="http://host.docker.internal:1234/v1" \
  -e PYTHONUNBUFFERED=1 \
  -v "$(pwd)/tests/generated:/app/tests/generated" \
  testing-llm-automation-engine
```

### Run with Ollama

Run the container using Ollama as the provider (Ollama must be running on your host at port 11434):

```bash
docker run -p 7860:7860 \
  --name testing-llm-automation-engine \
  --add-host=host.docker.internal:host-gateway \
  -e LLM_PROVIDER="ollama" \
  -e OLLAMA_URL="http://host.docker.internal:11434/v1" \
  -e PYTHONUNBUFFERED=1 \
  testing-llm-automation-engine
```

## Manual Debugging & Healing Workflow

This workflow simulates a CI/CD environment locally to debug flaky tests, analyze failure reports, and run the self-healing agent manually.

### Step 1: Launch the Container with Volume Mount

Run the Docker container with a volume mount to enable file editing from your host machine:

```bash
docker run -d -p 7860:7860 \
  --name testing-llm-automation-engine \
  --add-host=host.docker.internal:host-gateway \
  --env-file .env \
  -e LM_STUDIO_URL="http://host.docker.internal:1234/v1" \
  -e PYTHONUNBUFFERED=1 \
  -v "$(pwd)/tests/generated:/app/tests/generated" \
  testing-llm-automation-engine
```

The `-d` flag runs the container in detached mode, and `--name` assigns a name for easier reference.

### Step 2: Access the Container Shell

Get a command-line interface inside the container:

1. **Find the Container ID or Name:**

   ```bash
   docker ps
   ```

2. **Open the Shell:**

   ```bash
   docker exec -it testing-llm-automation-engine /bin/bash
   ```

   Or use the container ID:

   ```bash
   docker exec -it <CONTAINER_ID> /bin/bash
   ```

You are now inside the container (`root@<container-id>:/app#`).

### Step 3: Run Tests Manually (CLI)

Execute Playwright tests directly from the command line to verify failures:

**Run All Tests:**

```bash
npx playwright test
```

**Run a Specific Test:**

```bash
npx playwright test tests/generated/my_broken_test.spec.ts
```

**Run with Verbose Output:**

```bash
npx playwright test --reporter=list
```

### Step 4: Extract Test Reports

Copy the Playwright HTML report from the container to your host machine:

**On your Host Machine (not inside Docker):**

```bash
# Syntax: docker cp <ContainerName>:<PathInside> <PathOnHost>
docker cp testing-llm-automation-engine:/app/playwright-report ./playwright-report
```

**View the Report:**

```bash
open playwright-report/index.html
```

### Step 5: Run the Self-Healing Agent (CLI)

If a test fails, invoke the Healer agent manually to fix the code:

**Inside the Docker Shell:**

```bash
# Run healer with default 3 attempts (matches Web UI)
uv run python -m src.agents.healer tests/generated/my_broken_test.spec.ts

# Or run with custom retry limit
uv run python -m src.agents.healer tests/generated/my_broken_test.spec.ts --max-retries 5
```

**Expected Workflow:**

1. **Runs Test:** Executes the test and captures failure output
2. **Analyzes:** Sends error logs and code to LLM for analysis
3. **Heals:** Overwrites the file with the fixed code
4. **Verifies:** Runs the test again to confirm it passes

> **Note:** With the volume mount, fixes applied inside the container immediately appear in the file on your local machine (VS Code).

## Container Management

### Stop the Container

```bash
docker stop testing-llm-automation-engine
```

### Start a Stopped Container

```bash
docker start testing-llm-automation-engine
```

### Remove the Container

```bash
docker rm testing-llm-automation-engine
```

### View Container Logs

```bash
docker logs testing-llm-automation-engine
```

### Follow Logs in Real-Time

```bash
docker logs -f testing-llm-automation-engine
```

## Troubleshooting

### LM Studio Connection Issues

If the container cannot reach LM Studio on your host:

1. Ensure LM Studio is running on port 1234
2. Use `host.docker.internal` to connect to your host machine
3. Check firewall settings if needed

### Permission Issues

If you encounter permission errors with mounted volumes, adjust file permissions as needed.

### Container Won't Start

Check logs for errors:

```bash
docker logs testing-llm-automation-engine
```

### Port Already in Use

If port 7860 is already in use, use a different port:

```bash
docker run -p 7861:7860 ...
```

## Environment Variables

Key environment variables for Docker:

- `LLM_PROVIDER`: Service provider (`lm_studio` or `ollama`)
- `LM_STUDIO_URL`: LM Studio API endpoint (default: `http://localhost:1234/v1`)
- `OLLAMA_URL`: Ollama API endpoint (default: `http://localhost:11434/v1`)
- `LM_STUDIO_TEXT_MODEL` / `OLLAMA_TEXT_MODEL`: Text/code model name (e.g. `qwen/qwen3.6-35b-a3b` / `qwen3.6:latest`)
- `LM_STUDIO_VISION_MODEL` / `OLLAMA_VISION_MODEL`: Vision description model name (e.g. `google/gemma-4-26b-a4b` / `gemma4:26b`)
- `GRADIO_SERVER_NAME`: Set to `0.0.0.0` in Dockerfile for container access
- `PYTHONUNBUFFERED`: Set to `1` for real-time log output

See [env-variables.md](env-variables.md) for complete documentation.
