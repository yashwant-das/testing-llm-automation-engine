# Product Demo Guide: Testing LLM Automation Engine

> Follow this script to showcase the "Senior QA Engineer" intelligence of this agent in under 3 minutes.

---

## 🏁 Preparation

1. **Start Services**: Ensure LM Studio is running with your preferred model.
2. **Generate a "Dirty" Test**:

   ```bash
   python scripts/setup_demo.py
   ```

   _This creates `tests/generated/demo_broken.spec.ts` with an intentional locator bug._

---

## Demo Walkthrough

### 1. The Setup: "AI with Intent" (0:00 - 0:45)

- **Talk track**: "Most AI tools try to fix things blindly. I built a system that prioritizes **Explainability**. We’re going to take a standard Playwright test that fails due to a locator drift—a common nightmare for QA engineers."
- **Visual**: Open the broken test and point out the `#dfgasgfdfgh` (garbage) locator.

### 2. The Healing: "The Multi-Masked Agent" (0:45 - 1:30)

- **Talk track**: "I'm uploading this to the dashboard. My agent uses **Hybrid Intelligence**. It first uses a high-speed Python heuristic layer to scan the logs—this is 100% deterministic. If it finds a smoking gun, it saves LLM tokens and time."
- **Visual**: Click **Heal Test** in the Gradio UI.

### 3. The Core Value: "Explainable AI" (1:30 - 2:30)

- **Talk track**: "Look at the **Execution Timeline**. The agent didn't just 'guess.' It identified a `TIMEOUT` with **100% confidence** using regex. Then, it consulted the LLM to 'reason' a fix. See the **Decision JSON**? It explains exactly _why_ it chose the new selector."
- **Visual**: Scroll through the **Timeline** and expand the **Decision Inspector**.

### 4. The Closing: "Professional Toolchain" (2:30 - 3:00)

- **Talk track**: "The fix is applied and verified. A key differentiator here is the DX. We have a professional linting pipeline and Husky githooks protecting the repo. It's not just a script; it's an enterprise-ready framework."
- **Visual**: Show the passing test run and quickly peek at the [ARCHITECTURE.md](ARCHITECTURE.md) quality section.

---

## Key Architectural Highlights

- **Explainability**: "I explicitly designed the system to output evidence, reasoning summaries, code changes, and verification results as JSON artifacts."
- **Hybrid Intelligence**: "I balanced deterministic code (Regex) with probabilistic AI (LLM) to maximize speed and accuracy."
- **Full-Stack Quality**: "The project enforces Node.js and Python best practices via automated pre-commit hooks."
