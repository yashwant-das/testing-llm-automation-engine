# Product Demo Guide: Testing LLM Automation Engine

> Follow this script to showcase the "Senior QA Engineer" intelligence of this agent in under 3 minutes.

---

## Preparation

1. **Start Services**: Ensure LM Studio is running with your preferred model.
2. **Start the UI**:

   ```bash
   uv run python src/app.py
   ```

   Open `http://127.0.0.1:7860`.

3. **Generate a "Dirty" Test**:

   ```bash
   uv run python scripts/setup_demo.py
   ```

   _This creates `tests/generated/demo_broken.spec.ts` with an intentional locator bug._

---

## Demo Walkthrough

### 1. The Setup: "AI with Intent" (0:00 - 0:45)

- **Talk track**: "Most AI tools try to fix things blindly. I built a system that prioritizes **Explainability**. We’re going to take a standard Playwright test that fails due to a locator drift—a common nightmare for QA engineers."
- **Visual**: Open the broken test and point out the `#dfgasgfdfgh` (garbage) locator.

### 2. The Healing: "Hybrid Intelligence" (0:45 - 1:30)

- **Talk track**: "I'm uploading this to the dashboard. My agent uses **Hybrid Intelligence**. It first uses a high-speed Python heuristic layer to scan the logs—this is 100% deterministic. If it finds a smoking gun, it saves LLM tokens and time."
- **Visual**: Open the **Self-Healer** tab, upload `tests/generated/demo_broken.spec.ts`, leave **Max Healing Attempts** at `3`, and click **Heal Test**. Point out the center timeline as it streams the initial run, failure detection, evidence gathering, AI diagnosis, repair, and verification.

### 3. The Core Value: "Explainable AI" (1:30 - 2:30)

- **Talk track**: "Look at the **Healing Process Timeline**. The agent didn't just guess. It identified the failure pattern, gathered Playwright logs, captured available screenshot evidence, loaded DOM context from the test URL, and asked the LLM for a patch with a confidence score."
- **Visual**: In the right panel, show the **Explainable Report** first. Then open **Raw JSON Evidence** to show the persisted `HealingDecision` payload and verification result.

### 4. The Closing: "Professional Toolchain" (2:30 - 3:00)

- **Talk track**: "The fix is applied and verified through Playwright. A key differentiator here is the DX. We have a professional linting pipeline, Ruff-based Python checks, Markdownlint, ESLint, and Husky githooks protecting the repo. It's not just a script; it's an engineering workflow."
- **Visual**: Show the passing test run and quickly peek at the [ARCHITECTURE.md](ARCHITECTURE.md) quality section.

---

## Key Architectural Highlights

- **Explainability**: "I explicitly designed the system to output evidence, reasoning summaries, code changes, and verification results as JSON artifacts."
- **Hybrid Intelligence**: "I balanced deterministic code (Regex) with probabilistic AI (LLM) to maximize speed and accuracy."
- **Live Operations UI**: "The dashboard now streams timelines and separates controls, execution state, and artifacts, so users can see what each agent is doing while it runs."
- **Full-Stack Quality**: "The project enforces Node.js and Python best practices via automated pre-commit hooks."
