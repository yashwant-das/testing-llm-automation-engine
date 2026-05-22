# Testing LLM Automation Engine

> **An LLM-powered QA automation framework for Playwright test generation, visual UI understanding, and self-healing maintenance**

[![Python](https://img.shields.io/badge/Python-3.12%2B-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![TypeScript](https://img.shields.io/badge/TypeScript-5.9%2B-3178C6?logo=typescript&logoColor=white)](https://www.typescriptlang.org/)
[![Playwright](https://img.shields.io/badge/Playwright-1.57%2B-2EAD33?logo=playwright&logoColor=white)](https://playwright.dev/)
[![Gradio](https://img.shields.io/badge/Gradio-6.2%2B-FF6B6B?logo=gradio&logoColor=white)](https://gradio.app/)
[![ESLint](https://img.shields.io/badge/ESLint-9.39%2B-4B32C3?logo=eslint&logoColor=white)](https://eslint.org/)
[![Docker](https://img.shields.io/badge/Docker-Ready-2496ED?logo=docker&logoColor=white)](DOCKER.md)
[![License](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

## Problem Statement

Modern QA automation faces significant scalability challenges across the full test lifecycle:

1. **Test Creation**: Writing reliable browser tests from user stories and page context is repetitive and time-consuming.
2. **UI Understanding**: DOM-only inspection can miss visual layout, labels, and interaction cues that humans rely on.
3. **Test Maintenance**: Failing tests require teams to separate application defects, environment issues, locator drift, and flaky timing.

Many existing AI-based QA tools focus on only one part of this lifecycle or operate as "black boxes" without clear evidence for generated or repaired tests. **This lack of lifecycle coverage and explainability inhibits trust and complicates long-term maintenance.**

## Solution Overview

The **Testing LLM Automation Engine** is an intelligent QA framework designed to automate Playwright workflows across three complementary capabilities:

1. **Generate from DOM Context**: Uses a text/code LLM to create Playwright TypeScript tests from URLs, page structure, and user scenarios.
2. **Generate from Visual Context**: Uses a vision-capable LLM to interpret screenshots and produce tests when visual UI cues matter.
3. **Heal Existing Tests**: Diagnoses failing Playwright specs, proposes repairs, applies fixes, and records evidence-backed healing artifacts.

---

## Key Differentiators

What sets this framework apart from standard test automation tools?

- **Lifecycle Coverage**: Supports initial test generation, vision-assisted test creation, execution, and automated maintenance in one workflow.
- **Dual Generation Modes**: Combines DOM-driven generation for structured pages with screenshot-driven generation for visually rich interfaces.
- **Transparent Healing**: Every fix includes a `HealingDecision` JSON artifact, allowing you to trace exactly why a specific change was made.
- **Hybrid Diagnosis**: Combines **Deterministic Heuristics** (Regex) for instant, low-cost error detection with **LLM Reasoning** for complex failures.
- **Production-Ready Toolchain**: Ships with a proven quality control pipeline (ESLint 9, Flake8, Husky, lint-staged) to ensure maintainable, industry-standard code.

---

## Features

- **Automated Test Generation**: Analyzes DOM structures to generate robust Playwright TypeScript test suites.
- **Vision Agent**: Uses vision-capable LLMs (e.g., Qwen-VL) to understand UI from screenshots.
- **Self-Healing**: Automatically fixes broken tests by analyzing error logs and updating selectors. Supports sequential multi-step healing via the **Max Healing Attempts** configuration.
- **Enhanced Heuristics**: Deterministically identifies network errors, JavaScript runtime errors, and locator drift.
- **Customizable Prompts**: All LLM system instructions are externalized in the `prompts/` directory for easy tweaking.
- **Input Validation**: Comprehensive validation for URLs, file paths, and user inputs.
- **Interactive Dashboard**: Centralized Gradio interface for managing test generation, vision context, and healing operations.

---

## Confidence Scoring System

The agent assigns a **Confidence Score (0.0 - 1.0)** to every diagnosis to facilitate risk assessment:

- **1.0 (Deterministic)**: The failure matched a verified pattern (e.g., specific error codes). No probabilistic reasoning involved.
- **0.8 - 0.9 (High)**: The LLM identified the root cause with strong evidence from logs and code context.
- **< 0.7 (Low)**: The failure is ambiguous; the agent is proposing a "best-guess" fix that requires human review.

---

## Project Structure

```text
.
├── src/
│   ├── agents/          # Agent logic (Generator, Vision, Healer)
│   │   ├── generator.py # Test generation agent
│   │   ├── healer.py    # Self-healing agent
│   │   └── vision.py    # Vision-based test generation
│   ├── models/          # Data models and schemas
│   │   └── healing_model.py # Healing artifacts & execution timeline models
│   ├── utils/           # Shared utilities
│   │   ├── browser.py   # Browser automation (Playwright)
│   │   ├── llm.py       # LLM client configuration
│   │   ├── prompt_loader.py # Externalized prompt management
│   │   └── validation.py # Input validation utilities
│   └── app.py           # Unified Gradio UI
├── prompts/             # Externalized LLM system instructions (.md)
├── docs/                # Extended documentation
│   ├── ARCHITECTURE.md  # Deep dive into the agentic pipeline
│   ├── DEMO_GUIDE.md    # Scripted guide for a killing demo
│   └── HEALING_SCENARIOS.md # Story-driven examples of healing logic
├── tests/
│   ├── unit_test_*.py   # Logic & heuristic unit tests
│   ├── generated/       # Storage for generated .spec.ts files
│   ├── artifacts/       # Healing decisions and execution timelines
│   └── screenshots/     # Storage for Vision Agent debug screenshots
├── test-results/        # Playwright test execution results
├── playwright-report/   # Playwright HTML test reports
├── Dockerfile           # Docker container configuration
├── requirements.txt     # Python dependencies
├── package.json         # Node.js dependencies (Playwright)
├── playwright.config.ts # Playwright configuration
└── README.md            # This file
```

---

## Setup

### Option 1: Docker (Recommended)

The easiest way to run the application is using Docker.

```bash
# Build the Docker image
docker build -t testing-llm-automation-engine .

# Run the container
docker run -p 7860:7860 \
  --name testing-llm-automation-engine \
  --add-host=host.docker.internal:host-gateway \
  -e LM_STUDIO_URL="http://host.docker.internal:1234/v1" \
  -e LLM_PROVIDER="lm_studio" \
  testing-llm-automation-engine
```

**Or with Ollama:**

```bash
docker run -p 7860:7860 \
  --name testing-llm-automation-engine \
  --add-host=host.docker.internal:host-gateway \
  -e OLLAMA_URL="http://host.docker.internal:11434/v1" \
  -e LLM_PROVIDER="ollama" \
  testing-llm-automation-engine
```

Access the Gradio interface at `http://localhost:7860`. See [DOCKER.md](DOCKER.md) for more info.

### Option 2: Local Installation

1. **Install Python Dependencies** (Python 3.11+ recommended):

   ```bash
   pip install -r requirements.txt
   ```

2. **Install Node.js Dependencies**:

   ```bash
   npm install
   npx playwright install
   ```

3. **Configure LLM Provider**:
   Create a `.env` file and set `LLM_PROVIDER` to either `lm_studio` or `ollama`. Configure the corresponding URL and models.

---

## Usage

### Launch the UI

```bash
python src/app.py
```

Go to `http://127.0.0.1:7860` to generate, run, and heal tests.

<img width="2022" height="1324" alt="Screenshot 2026-01-30 at 10 40 13 PM" src="https://github.com/user-attachments/assets/71abaf56-78ae-44f6-bce1-f5d9413a48b4" />
<img width="2022" height="1324" alt="Screenshot 2026-01-30 at 10 40 38 PM" src="https://github.com/user-attachments/assets/c9a93fd7-c931-4738-a416-4568a6936932" />
<img width="2022" height="1324" alt="Screenshot 2026-01-30 at 10 42 47 PM" src="https://github.com/user-attachments/assets/d4ba59bb-1fed-41a2-9758-0765800f1aa4" />

### Running Agents Individually

```bash
python -m src.agents.healer tests/generated/broken_example.spec.ts
```

---

## Example Scenarios

### 1. Test Generator (Form Authentication)

- **URL**: [https://the-internet.herokuapp.com/login](https://the-internet.herokuapp.com/login)
- **Scenario**: Login with `tomsmith` and `SuperSecretPassword!`. Verify the success message appears.
- **Goal**: Proves the agent can handle standard HTML forms and success notifications.

### 2. Test Generator (Dynamic React Apps)

- **URL**: [https://demo.playwright.dev/todomvc/](https://demo.playwright.dev/todomvc/)
- **Scenario**: Add a todo item named 'Buy Milk'. Verify it appears in the list.
- **Goal**: Demonstrates capabilities with heavily dynamic, client-side rendered JavaScript apps.

### 3. Test Generator (Real-world Search)

- **URL**: [https://www.wikipedia.org](https://www.wikipedia.org)
- **Scenario**: Type 'AI' in the search input and press Enter. Verify that the URL contains 'Artificial_intelligence' and the main heading (h1) says 'Artificial intelligence'.
- **Goal**: Validates search interactions and multiple verification steps on professional sites.

### 4. Vision Agent

- **URL**: [https://www.saucedemo.com](https://www.saucedemo.com)
- **Scenario**: Login with `standard_user` / `secret_sauce`.
- **Goal**: Uses visual analysis to identify elements without relying solely on HTML source.

### 5. Self-Healer

- **Input**: A broken test file like `broken_example.spec.ts`.
- **Command**: `python -m src.agents.healer tests/generated/broken_example.spec.ts`
- **Goal**: Automatically repairs incorrect selectors and labels by analyzing Playwright error logs. Handles cascading fixes for multiple subsequent errors through a configurable **Max Healing Attempts** parameter.
- **Deep Dive**: See [HEALING_SCENARIOS.md](docs/HEALING_SCENARIOS.md) for a detailed breakdown of how the agent resolves specific failures like Locator Drift, Network Flakiness, and Race Conditions.
- **Trial**: To see it in action, purposefully introduce mistakes into the locator IDs or button names in the script and watch the agent heal them!

---

## Configuration & Quality Control

### Environment Variables

See [ENV_VARIABLES.md](ENV_VARIABLES.md) for full documentation on `LM_STUDIO_URL`, `DEFAULT_MODEL`, etc.

### Customizable Prompts

Edit the files in `prompts/` to tweak agent behavior without changing code:

- `generator.md`, `healer.md`, `vision.md`.

### Development Commands

```bash
npm run lint      # Run all quality checks
npm run test:unit # Run Python unit tests
npm run format    # Auto-format all code
```

### Tooling Stack

- **TypeScript/JS**: Prettier + ESLint (v9 Flat Config) + Playwright Plugin
- **Python**: Black + isort + Flake8
- **Documentation**: Markdownlint
- **Automation**: Husky (Git Hooks) + lint-staged

---

## Security

- Input validation prevents malicious URLs and path traversal.
- File operations restricted to allowed directories.
- Subprocess calls use proper sanitization.

---

## Architecture

See [ARCHITECTURE.md](docs/ARCHITECTURE.md) for a deep dive into the **Monitor -> Investigate -> Reason -> Act -> Report** pipeline.
