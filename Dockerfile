# syntax=docker/dockerfile:1
FROM mcr.microsoft.com/playwright/python:v1.57.0-noble

LABEL maintainer="QA Team" \
      description="Testing LLM Automation Engine"

WORKDIR /app

# Install Node.js with cache mount for faster rebuilds
RUN --mount=type=cache,target=/var/cache/apt,sharing=locked \
    --mount=type=cache,target=/var/lib/apt,sharing=locked \
    apt-get update && \
    apt-get install -y --no-install-recommends curl ca-certificates gnupg && \
    mkdir -p /etc/apt/keyrings && \
    curl -fsSL https://deb.nodesource.com/gpgkey/nodesource-repo.gpg.key | gpg --dearmor -o /etc/apt/keyrings/nodesource.gpg && \
    echo "deb [signed-by=/etc/apt/keyrings/nodesource.gpg] https://deb.nodesource.com/node_20.x nodistro main" | tee /etc/apt/sources.list.d/nodesource.list && \
    apt-get update && \
    apt-get install -y nodejs

# Set environment variables in a single layer
ENV PLAYWRIGHT_SKIP_BROWSER_DOWNLOAD=1 \
    GRADIO_SERVER_NAME="0.0.0.0" \
    GRADIO_SERVER_PORT=7860 \
    PYTHONUNBUFFERED=1

# Install Node.js dependencies with cache mount
COPY package.json package-lock.json ./
RUN --mount=type=cache,target=/root/.npm \
    npm ci

# Install uv for high-performance dependency management
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# Install Python dependencies with cache mount
COPY pyproject.toml uv.lock ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-cache

# Copy configuration files
COPY playwright.config.ts tsconfig.json ./

# Copy application source code and required resources
COPY src/ ./src/
COPY prompts/ ./prompts/
COPY schemas/ ./schemas/
COPY scripts/ ./scripts/
COPY benchmarks/ ./benchmarks/

EXPOSE 7860

CMD ["uv", "run", "src/app.py"]