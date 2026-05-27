"""
Gradio web interface for the Testing LLM Automation Engine.

Provides three main tabs:
- Test Generator: Generate Playwright tests from URL and description
- Vision Agent: Generate tests using vision-capable LLMs
- Self-Healer: Automatically repair broken test files
"""

import os
import sys
from pathlib import Path

# Add the project root to sys.path to support 'src.' imports when run as a script
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.append(str(PROJECT_ROOT))

import logging

import gradio as gr

# Configure structured logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)

import src.utils.validation as validation_utils
from src.utils.llm import extract_code_block, get_client, get_model
from src.utils.prompt_loader import load_prompt
from src.utils.validation import ValidationError

# Custom CSS matching Gradio website style
css = """
.tall-textbox textarea { min-height: 300px !important; }
.tall-code .code-container { min-height: 400px !important; }
/* Match Gradio website typography and spacing */
h1 {
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
    font-weight: 600;
    letter-spacing: -0.025em;
}
/* Clean component styling */
.gradio-container {
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
}
"""

# Use default theme for standard Gradio appearance
with gr.Blocks(title="Testing LLM Automation Engine") as demo:
    gr.Markdown("# Testing LLM Automation Engine")
    gr.Markdown("Generate, test, and maintain Playwright test automation scripts.")

    with gr.Tabs():
        # Tab 1: Test Generator
        with gr.Tab("Test Generator"):
            with gr.Row():
                # Column 1: Controls
                with gr.Column(scale=3):
                    url_in = gr.Textbox(
                        label="Target URL",
                        placeholder="https://example.com",
                        value="https://the-internet.herokuapp.com/login",
                    )
                    story_in = gr.Textbox(
                        label="Test Scenario",
                        placeholder="Describe the test scenario...",
                        value="Login with tomsmith and SuperSecretPassword!. Verify success message.",
                        lines=3,
                    )
                    with gr.Row():
                        gen_btn = gr.Button("Generate Test", variant="primary")
                        run_btn = gr.Button("Run Test", variant="secondary")

                # Column 2: Live Execution Center
                with gr.Column(scale=4):
                    gen_timeline = gr.Markdown(
                        "### ⏱️ Generation Timeline\n*Ready to generate...*"
                    )

                # Column 3: Artifact Inspector
                with gr.Column(scale=5):
                    with gr.Tabs():
                        with gr.Tab("Generated Code"):
                            code_out = gr.Code(
                                label="TypeScript Code",
                                language="typescript",
                                lines=20,
                                elem_classes=["tall-code"],
                            )
                        with gr.Tab("Execution Logs"):
                            result_out = gr.Textbox(
                                label="Execution Log Output",
                                interactive=False,
                                lines=20,
                                elem_classes=["tall-textbox"],
                            )

            def safe_generate_test(url, story):
                """Generate test script with input validation and error handling, streaming progress."""
                timeline = "### ⏱️ Generation Timeline\n\n"

                timeline += "🟢 **Input Validation**: Verifying target URL and user story...\n\n"
                yield timeline, ""

                try:
                    validated_url = validation_utils.validate_and_sanitize_url(url)
                    validated_story = validation_utils.validate_description(story)
                except ValidationError as e:
                    yield (
                        timeline + f"🔴 **Validation Error**: {str(e)}",
                        f"Validation Error: {str(e)}",
                    )
                    return
                except Exception as e:
                    yield timeline + f"🔴 **Error**: {str(e)}", f"Error: {str(e)}"
                    return

                timeline += "🟢 **Scanning Web Page**: Accessing Chromium browser to capture DOM layout...\n\n"
                yield timeline, ""

                try:
                    from src.utils.browser import fetch_page_context

                    html_context = fetch_page_context(validated_url)
                    if "Error" in html_context:
                        yield (
                            timeline + f"🔴 **Scanning Error**: {html_context}",
                            f"Scanning Error: {html_context}",
                        )
                        return
                except Exception as e:
                    yield (
                        timeline + f"🔴 **Scanning Error**: {str(e)}",
                        f"Error: {str(e)}",
                    )
                    return

                timeline += "🟢 **Synthesizing Instructions**: Preparing prompt models and DOM inputs...\n\n"
                yield timeline, ""

                try:
                    system_instruction = load_prompt("generator")
                    user_prompt = f"""
    TARGET URL: {validated_url}
    USER STORY: {validated_story}
    PAGE CONTEXT: {html_context}
    """
                except Exception as e:
                    yield (
                        timeline + f"🔴 **Error loading prompts**: {str(e)}",
                        f"Error: {str(e)}",
                    )
                    return

                timeline += "🧠 **LLM Inference**: Engineering script structure and selectors...\n\n"
                yield timeline, ""

                try:
                    client = get_client()
                    response = client.chat.completions.create(
                        model=get_model(),
                        messages=[
                            {"role": "system", "content": system_instruction},
                            {"role": "user", "content": user_prompt},
                        ],
                        temperature=0.1,
                    )

                    if not response.choices or not response.choices[0].message.content:
                        yield (
                            timeline + "🔴 **LLM Error**: Empty response",
                            "Error: LLM returned empty response",
                        )
                        return

                    raw_content = response.choices[0].message.content
                    code = extract_code_block(raw_content)

                    if not code:
                        yield (
                            timeline
                            + "🔴 **Code Extraction Error**: No code block found",
                            "Error: Could not extract code block from LLM response",
                        )
                        return
                except Exception as e:
                    yield (
                        timeline + f"🔴 **LLM Error**: {str(e)}",
                        f"LLM Error: {str(e)}",
                    )
                    return

                timeline += "✅ **Success**: Test script successfully generated!\n\n"
                yield timeline, code

            def safe_run_test(url, code, story):
                """Run generated test with input validation and error handling, streaming progress."""
                timeline = "### ⏱️ Test Execution Timeline\n\n"
                timeline += "🟢 **Sanity Checks**: Verifying script inputs...\n\n"
                yield timeline, ""

                if not code or not code.strip():
                    yield (
                        timeline + "🔴 **Input Error**: No test code provided",
                        "Error: No test code provided",
                    )
                    return

                try:
                    validated_url = validation_utils.validate_and_sanitize_url(url)
                    validated_story = (
                        validation_utils.validate_description(story)
                        if story
                        else "test"
                    )
                except ValidationError as e:
                    yield (
                        timeline + f"🔴 **Validation Error**: {str(e)}",
                        f"Validation Error: {str(e)}",
                    )
                    return
                except Exception as e:
                    yield timeline + f"🔴 **Error**: {str(e)}", f"Error: {str(e)}"
                    return

                timeline += (
                    "🟢 **Writing Spec File**: Saving test script to workspace...\n\n"
                )
                yield timeline, ""

                try:
                    import re
                    from datetime import datetime

                    from src.utils.browser import extract_domain

                    domain = extract_domain(validated_url)
                    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                    clean_desc = re.sub(r"[^a-zA-Z0-9]", "_", validated_story).lower()
                    clean_desc = re.sub(r"_+", "_", clean_desc)
                    snake_desc = clean_desc[:40].strip("_")
                    filename = f"{domain}_{snake_desc}_{timestamp}.spec.ts"

                    test_dir = "tests/generated"
                    os.makedirs(test_dir, exist_ok=True)
                    filepath = os.path.join(test_dir, filename)

                    with open(filepath, "w", encoding="utf-8") as f:
                        f.write(code)
                except Exception as e:
                    yield (
                        timeline + f"🔴 **File Error**: {str(e)}",
                        f"Error writing file: {str(e)}",
                    )
                    return

                timeline += f"🟢 **Playwright Test Runner**: Launching `npx playwright test {filename}`...\n\n"
                yield timeline, "Running tests in workspace..."

                try:
                    import subprocess

                    from src.utils.formatting import format_test_result

                    result = subprocess.run(
                        ["npx", "playwright", "test", filepath],
                        capture_output=True,
                        text=True,
                        timeout=45,
                        cwd=str(PROJECT_ROOT),  # Project root
                    )

                    if result.returncode == 0:
                        timeline += (
                            "✅ **Test Passed**: Spec file ran successfully!\n\n"
                        )
                        logs = format_test_result(filepath, result.stdout, success=True)
                        yield timeline, logs
                    else:
                        timeline += "❌ **Test Failed**: Playwright returned non-zero exit code.\n\n"
                        raw_logs = result.stdout if result.stdout else result.stderr
                        logs = format_test_result(filepath, raw_logs, success=False)
                        yield timeline, logs
                except subprocess.TimeoutExpired:
                    timeline += "🔴 **Timeout Error**: Playwright test timed out after 45 seconds.\n\n"
                    yield (
                        timeline,
                        f"Error: Test execution timed out after 45 seconds.\nStored in: {filepath}",
                    )
                except FileNotFoundError:
                    timeline += (
                        "🔴 **Environment Error**: Playwright executable not found.\n\n"
                    )
                    yield (
                        timeline,
                        "Error: Playwright not found. Please run 'npx playwright install'",
                    )
                except Exception as e:
                    timeline += f"🔴 **Execution Error**: {str(e)}\n\n"
                    yield timeline, f"Execution Error: {str(e)}\nStored in: {filepath}"

            gen_btn.click(
                fn=safe_generate_test,
                inputs=[url_in, story_in],
                outputs=[gen_timeline, code_out],
            )
            run_btn.click(
                fn=safe_run_test,
                inputs=[url_in, code_out, story_in],
                outputs=[gen_timeline, result_out],
            )

        # Tab 2: Vision Agent
        with gr.Tab("Vision Agent"):
            with gr.Row():
                # Column 1: Controls
                with gr.Column(scale=3):
                    v_url_in = gr.Textbox(
                        label="Target URL",
                        placeholder="https://example.com",
                        value="https://www.saucedemo.com",
                    )
                    v_story_in = gr.Textbox(
                        label="Instruction",
                        placeholder="Describe the action to perform...",
                        value="Login with standard_user / secret_sauce",
                        lines=2,
                    )
                    with gr.Row():
                        v_btn = gr.Button("Capture & Analyze", variant="primary")
                        v_run_btn = gr.Button("Run Test", variant="secondary")

                # Column 2: Live Execution Center
                with gr.Column(scale=4):
                    v_timeline = gr.Markdown(
                        "### ⏱️ Visual Timeline\n*Ready to capture screenshot...*"
                    )

                # Column 3: Artifact Inspector
                with gr.Column(scale=5):
                    with gr.Tabs():
                        with gr.Tab("Captured View"):
                            v_image_preview = gr.Image(
                                label="Screenshot Preview",
                                type="filepath",
                                interactive=False,
                            )
                        with gr.Tab("Generated Code"):
                            v_code_out = gr.Code(
                                label="TypeScript Code",
                                language="typescript",
                                lines=20,
                                elem_classes=["tall-code"],
                            )
                        with gr.Tab("Execution Logs"):
                            v_result_out = gr.Textbox(
                                label="Execution Log Output",
                                interactive=False,
                                lines=20,
                                elem_classes=["tall-textbox"],
                            )

            def safe_analyze_visual(url, instruction):
                """Analyze UI visually with input validation, streaming progress, and screenshot preview."""
                timeline = "### ⏱️ Visual Timeline\n\n"

                timeline += "🟢 **Input Validation**: Verifying target URL and instruction...\n\n"
                yield timeline, None, ""

                try:
                    validated_url = validation_utils.validate_and_sanitize_url(url)
                    validated_instruction = validation_utils.validate_description(
                        instruction
                    )
                except ValidationError as e:
                    yield (
                        timeline + f"🔴 **Validation Error**: {str(e)}",
                        None,
                        f"Validation Error: {str(e)}",
                    )
                    return
                except Exception as e:
                    yield timeline + f"🔴 **Error**: {str(e)}", None, f"Error: {str(e)}"
                    return

                timeline += "🟢 **Chromium Browser Initialization**: Pre-heating headless runner...\n\n"
                yield timeline, None, ""

                import re
                import time
                from datetime import datetime

                from playwright.sync_api import sync_playwright

                from src.utils.browser import extract_domain

                screenshot_dir = "tests/screenshots"
                os.makedirs(screenshot_dir, exist_ok=True)

                domain = extract_domain(validated_url)
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                clean_inst = re.sub(
                    r"[^a-zA-Z0-9\s]", "", validated_instruction
                ).lower()
                snake_inst = "_".join(clean_inst.split())[:30]
                screenshot_name = f"{domain}_{snake_inst}_{timestamp}.png"
                screenshot_path = os.path.join(screenshot_dir, screenshot_name)

                timeline += "🟢 **Screenshot Capturing**: Navigating page and rendering view...\n\n"
                yield timeline, None, ""

                try:
                    with sync_playwright() as p:
                        browser = p.chromium.launch(headless=True)
                        context = browser.new_context(
                            viewport={"width": 1280, "height": 720}
                        )
                        page = context.new_page()
                        page.goto(
                            validated_url, timeout=30000, wait_until="domcontentloaded"
                        )
                        time.sleep(2)  # Wait for animations
                        page.screenshot(path=screenshot_path)
                        browser.close()
                except Exception as e:
                    yield (
                        timeline + f"🔴 **Browser Capture Error**: {str(e)}",
                        None,
                        f"Error capturing screenshot: {str(e)}",
                    )
                    return

                if not os.path.exists(screenshot_path):
                    yield (
                        timeline + "🔴 **Browser Error**: Screenshot creation failed",
                        None,
                        f"Error: Screenshot was not created at {screenshot_path}",
                    )
                    return

                timeline += (
                    "🖼️ **Screenshot Captured**: Displaying active viewport render!\n\n"
                )
                yield timeline, screenshot_path, ""

                timeline += "🟢 **Encoding Screenshot**: Compressing image bytes to base64...\n\n"
                yield timeline, screenshot_path, ""

                try:
                    import base64

                    with open(screenshot_path, "rb") as image_file:
                        base64_image = base64.b64encode(image_file.read()).decode(
                            "utf-8"
                        )
                except Exception as e:
                    yield (
                        timeline + f"🔴 **Encoding Error**: {str(e)}",
                        screenshot_path,
                        f"Error: {str(e)}",
                    )
                    return

                timeline += "🧠 **Visual AI Inference**: Calling vision LLM to interpret UI layout...\n\n"
                yield timeline, screenshot_path, ""

                try:
                    system_instruction = load_prompt("vision")
                    client = get_client()
                    response = client.chat.completions.create(
                        model=get_model(vision=True),
                        messages=[
                            {"role": "system", "content": system_instruction},
                            {
                                "role": "user",
                                "content": [
                                    {
                                        "type": "text",
                                        "text": f"TARGET URL: {validated_url}\nUser Scenario: {validated_instruction}",
                                    },
                                    {
                                        "type": "image_url",
                                        "image_url": {
                                            "url": f"data:image/png;base64,{base64_image}"
                                        },
                                    },
                                ],
                            },
                        ],
                        temperature=0.1,
                        max_tokens=2000,
                    )

                    if not response.choices or not response.choices[0].message.content:
                        yield (
                            timeline
                            + "🔴 **LLM Error**: Vision model returned empty response",
                            screenshot_path,
                            "Error: Vision LLM returned empty response",
                        )
                        return

                    code = extract_code_block(response.choices[0].message.content)
                    if not code:
                        yield (
                            timeline
                            + "🔴 **Code Extraction Error**: No code block found",
                            screenshot_path,
                            "Error: Could not extract code block from vision LLM response",
                        )
                        return
                except Exception as e:
                    yield (
                        timeline + f"🔴 **LLM Error**: {str(e)}",
                        screenshot_path,
                        f"Vision LLM Error: {str(e)}",
                    )
                    return

                timeline += "✅ **Success**: Visual-based test script successfully generated!\n\n"
                yield timeline, screenshot_path, code

            def safe_run_vision_test(url, code, instruction):
                """Run vision test, streaming progress to the visual timeline."""
                for timeline_val, logs_val in safe_run_test(url, code, instruction):
                    timeline_val = timeline_val.replace(
                        "Test Execution Timeline", "Visual Test Execution Timeline"
                    )
                    yield timeline_val, logs_val

            v_btn.click(
                fn=safe_analyze_visual,
                inputs=[v_url_in, v_story_in],
                outputs=[v_timeline, v_image_preview, v_code_out],
            )
            v_run_btn.click(
                fn=safe_run_vision_test,
                inputs=[v_url_in, v_code_out, v_story_in],
                outputs=[v_timeline, v_result_out],
            )

        # Tab 3: Self-Healer
        with gr.Tab("Self-Healer"):
            with gr.Row():
                # Column 1: Controls
                with gr.Column(scale=3):
                    h_file_in = gr.File(
                        label="Test File", file_types=[".ts"], file_count="single"
                    )
                    h_max_retries_in = gr.Slider(
                        minimum=1,
                        maximum=5,
                        value=3,
                        step=1,
                        label="Max Healing Attempts",
                    )
                    h_btn = gr.Button("Heal Test", variant="primary")

                # Column 2: Live Execution Center
                with gr.Column(scale=4):
                    h_timeline_out = gr.Markdown(
                        "### ⏱️ Healing Process Timeline\n*Ready to load spec and heal...*"
                    )

                # Column 3: Artifact Inspector
                with gr.Column(scale=5):
                    with gr.Tabs():
                        with gr.Tab("Explainable Report"):
                            h_explanation_out = gr.Markdown(
                                "### 🧠 AI Healing Explanation\n*No healer run active.*"
                            )
                        with gr.Tab("Execution Logs"):
                            h_result_out = gr.Textbox(
                                label="Execution Log Output",
                                interactive=False,
                                lines=20,
                                elem_classes=["tall-textbox"],
                            )
                        with gr.Tab("Raw JSON Evidence"):
                            with gr.Accordion(
                                "Raw JSON Decision & Artifacts", open=False
                            ):
                                h_decision_out = gr.JSON(label="Raw JSON")

            def wrap_healer(file_obj, max_retries):
                """Handle file upload from Gradio and attempt to heal the test file, streaming progressive updates."""
                timeline_md = "### ⏱️ Healing Process Timeline\n\n"

                if file_obj is None:
                    yield (
                        "Please upload a test file.",
                        "### 🧠 AI Healing Explanation\n*No healer run active.*",
                        timeline_md + "🔴 **No file uploaded**",
                        None,
                    )
                    return

                try:
                    import shutil

                    # Resolve path
                    file_path = file_obj if isinstance(file_obj, str) else file_obj.name
                    local_path = os.path.join(
                        "tests", "generated", os.path.basename(file_path)
                    )
                    validated_path = validation_utils.validate_file_path(local_path)
                    shutil.copy(file_path, validated_path)

                    timeline_md += f"🟢 **File Uploaded**: Saved to workspace path `{os.path.basename(validated_path)}`...\n\n"
                    yield (
                        "Initializing healing...",
                        "### 🧠 AI Healing Explanation\n*No healer run active.*",
                        timeline_md,
                        None,
                    )

                    from src.agents.healer import (
                        analyze_and_plan,
                        apply_fix,
                        emit_artifacts,
                        gather_evidence,
                        run_test,
                    )
                    from src.models.healing_model import (
                        ExecutionTimeline,
                        FailureType,
                        HealingAction,
                        HealingDecision,
                    )

                    timeline = ExecutionTimeline()
                    timeline.add_step(
                        "Start", f"Healing session started for {validated_path}"
                    )

                    timeline_md += "🟢 **Initial Verification Run**: Launching test to capture failure signature...\n\n"
                    yield (
                        "Running initial test...",
                        "### 🧠 AI Healing Explanation\n*No healer run active.*",
                        timeline_md,
                        None,
                    )

                    # Run initial test
                    result = run_test(validated_path)

                    if result.returncode == 0:
                        timeline.add_step(
                            "InitialRun", "Test passed, no healing needed"
                        )
                        timeline_md += "✅ **No Healing Needed**: Test passed on the first run!\n\n"

                        success_decision = HealingDecision(
                            test_file=validated_path,
                            failure_type=FailureType.UNKNOWN,
                            failure_summary="Test passed initially",
                            evidence=gather_evidence(validated_path, result),
                            hypothesis="No repairs needed.",
                            confidence_score=1.0,
                            reasoning_steps=["Initial execution passed."],
                            action_taken=HealingAction(
                                original_code="", fixed_code="", description="None"
                            ),
                            verification_passed=True,
                        )
                        emit_artifacts(success_decision, timeline)

                        yield (
                            "Test passed (No healing needed).",
                            success_decision.to_markdown(),
                            timeline_md,
                            success_decision.to_dict(),
                        )
                        return

                    timeline.add_step(
                        "FailureDetected",
                        f"Initial test run failed with return code {result.returncode}",
                    )
                    timeline_md += f"❌ **Failure Detected**: Test failed (exit code {result.returncode}). Gaining diagnostic context...\n\n"
                    yield (
                        "Analyzing failure...",
                        "### 🧠 AI Healing Explanation\n*No healer run active.*",
                        timeline_md,
                        None,
                    )

                    # Read code
                    with open(validated_path, "r", encoding="utf-8") as f:
                        current_code = f.read()

                    latest_decision = None

                    # Retries loop
                    for attempt in range(int(max_retries)):
                        attempt_num = attempt + 1
                        timeline_md += f"🟢 **Attempt {attempt_num}/{max_retries}**: Initiating healing attempt...\n\n"
                        timeline.add_step(
                            "HealingAttempt", f"Starting attempt {attempt_num}"
                        )
                        yield (
                            f"Healing attempt {attempt_num}...",
                            "### 🧠 AI Healing Explanation\n*No healer run active.*",
                            timeline_md,
                            None,
                        )

                        # Gather evidence
                        timeline_md += f"🟢 **Evidence Gathering (Attempt {attempt_num})**: Loading logs, screenshot, and page HTML DOM...\n\n"
                        yield (
                            f"Attempt {attempt_num}: Gathering evidence...",
                            "### 🧠 AI Healing Explanation\n*No healer run active.*",
                            timeline_md,
                            None,
                        )
                        evidence = gather_evidence(validated_path, result)
                        timeline.add_step(
                            "EvidenceCollected",
                            "Logs and screenshot (if available) collected",
                        )

                        # Reason & Plan
                        timeline_md += f"🧠 **AI Diagnostic Reasoning (Attempt {attempt_num})**: Synthesizing failure classification and resolution strategy...\n\n"
                        yield (
                            f"Attempt {attempt_num}: Reasoning and planning...",
                            "### 🧠 AI Healing Explanation\n*No healer run active.*",
                            timeline_md,
                            None,
                        )

                        decision = analyze_and_plan(
                            validated_path, current_code, evidence
                        )
                        latest_decision = decision
                        timeline.add_step(
                            "AnalysisComplete",
                            f"Diagnosed as {decision.failure_type}. Hypothesis: {decision.hypothesis}",
                        )

                        timeline_md += f'🧠 **AI Hypothesis**: *"{decision.hypothesis}"* (Confidence: {int(decision.confidence_score * 100)}%)\n\n'
                        yield (
                            f"Attempt {attempt_num}: Proposing code repair...",
                            "### 🧠 AI Healing Explanation\n*No healer run active.*",
                            timeline_md,
                            None,
                        )

                        # Apply fix
                        new_code = apply_fix(validated_path, current_code, decision)

                        if new_code == current_code:
                            decision.verification_log = (
                                "Could not apply fix (code mismatch)"
                            )
                            timeline.add_step(
                                "ActionFailed",
                                "Proposed fix could not be applied (target code not found)",
                            )
                            emit_artifacts(decision, timeline)

                            timeline_md += "🔴 **Apply Repair Failed**: Match block indentation/whitespace mismatch.\n\n"
                            yield (
                                f"Attempt {attempt_num} failed.",
                                decision.to_markdown(),
                                timeline_md,
                                decision.to_dict(),
                            )
                            continue

                        timeline_md += f'🛠️ **Repair Applied**: Selector replaced: *"{decision.action_taken.description}"*...\n\n'
                        timeline.add_step(
                            "SelectorUpdated",
                            f"Applied fix: {decision.action_taken.description}",
                        )
                        yield (
                            f"Attempt {attempt_num}: Saving changes...",
                            "### 🧠 AI Healing Explanation\n*No healer run active.*",
                            timeline_md,
                            None,
                        )

                        # Write new code
                        with open(validated_path, "w", encoding="utf-8") as f:
                            f.write(new_code)

                        # Verify
                        timeline_md += f"🟢 **Verification Run (Attempt {attempt_num})**: Re-running test script inside workspace...\n\n"
                        yield (
                            f"Attempt {attempt_num}: Verifying repair...",
                            "### 🧠 AI Healing Explanation\n*No healer run active.*",
                            timeline_md,
                            None,
                        )

                        verify_result = run_test(validated_path)
                        decision.verification_passed = verify_result.returncode == 0
                        decision.verification_log = (
                            verify_result.stdout
                            if verify_result.returncode == 0
                            else verify_result.stderr
                        )

                        if decision.verification_passed:
                            timeline.add_step("Verification", "Test passed on re-run")
                            timeline_md += "✅ **Verification Passed**: Repaired test successfully verified on re-run!\n\n"
                        else:
                            timeline.add_step("Verification", "Test failed on re-run")
                            timeline_md += "❌ **Verification Failed**: Test failed again on re-run.\n\n"

                        emit_artifacts(decision, timeline)

                        if decision.verification_passed:
                            yield (
                                f"SUCCESS: Test healed! \nReasoning: {decision.hypothesis}",
                                decision.to_markdown(),
                                timeline_md,
                                decision.to_dict(),
                            )
                            return

                        # Prepare next loop
                        current_code = new_code
                        result = verify_result
                        timeline.add_step("Retry", "Preparing for next retry attempt")

                    timeline.add_step(
                        "HealingFailed",
                        f"Exhausted {max_retries} attempts without success",
                    )
                    timeline_md += "🔴 **Healing Failed**: Bounded execution limit reached without achieving verification pass.\n\n"

                    md_report = (
                        latest_decision.to_markdown()
                        if latest_decision
                        else "### Healing Failed"
                    )
                    yield (
                        "Healing failed to make test pass.",
                        md_report,
                        timeline_md,
                        latest_decision.to_dict() if latest_decision else None,
                    )

                except ValidationError as e:
                    yield (
                        f"Validation Error: {str(e)}",
                        "### 🧠 AI Healing Explanation\n*Validation error occurred.*",
                        timeline_md + f"🔴 **Validation Error**: {str(e)}",
                        None,
                    )
                except Exception as e:
                    yield (
                        f"Error: {str(e)}",
                        "### 🧠 AI Healing Explanation\n*An error occurred.*",
                        timeline_md + f"🔴 **Error**: {str(e)}",
                        None,
                    )

            h_btn.click(
                fn=wrap_healer,
                inputs=[h_file_in, h_max_retries_in],
                outputs=[
                    h_result_out,
                    h_explanation_out,
                    h_timeline_out,
                    h_decision_out,
                ],
            )

if __name__ == "__main__":
    demo.launch(theme=gr.themes.Default(), css=css)
