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
import shutil

import gradio as gr

# Configure structured logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)

import src.utils.validation as validation_utils
from src.agents.generator import generate_test_script, run_generated_test
from src.agents.healer import attempt_healing
from src.agents.vision import analyze_visual_ui
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
                with gr.Column(scale=1):
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
                    gen_btn = gr.Button("Generate Test", variant="primary")

                with gr.Column(scale=1):
                    code_out = gr.Code(
                        label="Generated Code",
                        language="typescript",
                        lines=20,
                        elem_classes=["tall-code"],
                    )
                    with gr.Row():
                        run_btn = gr.Button("Run Test", variant="secondary")
                    result_out = gr.Textbox(
                        label="Execution Result",
                        interactive=False,
                        lines=12,
                        elem_classes=["tall-textbox"],
                    )

            def safe_generate_test(url, story):
                """Generate test script with input validation and error handling."""
                try:
                    validated_url = validation_utils.validate_and_sanitize_url(url)
                    validated_story = validation_utils.validate_description(story)
                    return generate_test_script(validated_url, validated_story)
                except ValidationError as e:
                    return f"Validation Error: {str(e)}"
                except Exception as e:
                    return f"Error: {str(e)}"

            def safe_run_test(url, code, story):
                """Run generated test with input validation and error handling."""
                try:
                    validated_url = validation_utils.validate_and_sanitize_url(url)
                    validated_story = (
                        validation_utils.validate_description(story)
                        if story
                        else "test"
                    )
                    return run_generated_test(validated_url, code, validated_story)
                except ValidationError as e:
                    return f"Validation Error: {str(e)}"
                except Exception as e:
                    return f"Error: {str(e)}"

            gen_btn.click(
                fn=safe_generate_test, inputs=[url_in, story_in], outputs=code_out
            )
            run_btn.click(
                fn=safe_run_test,
                inputs=[url_in, code_out, story_in],
                outputs=result_out,
            )

        # Tab 2: Vision Agent
        with gr.Tab("Vision Agent"):
            gr.Markdown(
                "Generate tests using vision-capable LLMs to analyze UI screenshots."
            )
            with gr.Row():
                with gr.Column(scale=1):
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
                    v_btn = gr.Button("Capture & Analyze", variant="primary")

                with gr.Column(scale=1):
                    v_code_out = gr.Code(
                        language="typescript",
                        label="Generated Code",
                        lines=20,
                        elem_classes=["tall-code"],
                    )
                    with gr.Row():
                        v_run_btn = gr.Button("Run Test", variant="secondary")
                    v_result_out = gr.Textbox(
                        label="Execution Result",
                        interactive=False,
                        lines=10,
                        elem_classes=["tall-textbox"],
                    )

            def safe_analyze_visual(url, instruction):
                """Analyze UI visually with input validation and error handling."""
                try:
                    validated_url = validation_utils.validate_and_sanitize_url(url)
                    validated_instruction = validation_utils.validate_description(
                        instruction
                    )
                    return analyze_visual_ui(validated_url, validated_instruction)
                except ValidationError as e:
                    return f"Validation Error: {str(e)}"
                except Exception as e:
                    return f"Error: {str(e)}"

            def safe_run_vision_test(url, code, instruction):
                """Run vision-generated test with input validation and error handling."""
                try:
                    validated_url = validation_utils.validate_and_sanitize_url(url)
                    validated_instruction = (
                        validation_utils.validate_description(instruction)
                        if instruction
                        else "test"
                    )
                    return run_generated_test(
                        validated_url, code, validated_instruction
                    )
                except ValidationError as e:
                    return f"Validation Error: {str(e)}"
                except Exception as e:
                    return f"Error: {str(e)}"

            v_btn.click(
                fn=safe_analyze_visual,
                inputs=[v_url_in, v_story_in],
                outputs=v_code_out,
            )
            v_run_btn.click(
                fn=safe_run_vision_test,
                inputs=[v_url_in, v_code_out, v_story_in],
                outputs=v_result_out,
            )

        # Tab 3: Self-Healer
        with gr.Tab("Self-Healer"):
            gr.Markdown(
                "Automatically repair broken Playwright tests by analyzing error logs."
            )
            with gr.Row():
                with gr.Column(scale=1):
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
                    h_timeline_out = gr.Markdown("### ⏱️ Timeline will appear here...")

                with gr.Column(scale=1):
                    h_decision_out = gr.JSON(label="Healing Decision")
                    h_result_out = gr.Textbox(
                        label="Result",
                        interactive=False,
                        lines=10,
                        elem_classes=["tall-textbox"],
                    )

            def get_latest_artifacts():
                """Scan ARTIFACTS_DIR for the most recent healing decision and timeline.

                Returns:
                    tuple: (decision_data, timeline_md) or (None, None) if not found
                """
                artifacts_dir = "tests/artifacts"
                if not os.path.exists(artifacts_dir):
                    return None, None

                try:
                    files = os.listdir(artifacts_dir)
                    decisions = [
                        f
                        for f in files
                        if f.startswith("healing_decision_") and f.endswith(".json")
                    ]
                    timelines = [
                        f
                        for f in files
                        if f.startswith("execution_timeline_") and f.endswith(".json")
                    ]

                    decisions.sort(reverse=True)
                    timelines.sort(reverse=True)

                    decision_data = None
                    timeline_md = ""

                    import json

                    if decisions:
                        with open(os.path.join(artifacts_dir, decisions[0]), "r") as f:
                            decision_data = json.load(f)

                    if timelines:
                        with open(os.path.join(artifacts_dir, timelines[0]), "r") as f:
                            tl_data = json.load(f)
                            steps = tl_data.get("steps", [])
                            md_lines = ["### ⏱️ Execution Timeline"]
                            for step in steps:
                                # Simple formatting: "StepName: Details"
                                name = step.get("step", "Unknown")
                                det = step.get("details", "")
                                icon = "🟢"
                                if "Fail" in name or "Error" in name:
                                    icon = "🔴"
                                if "Warn" in name or "Retry" in name:
                                    icon = "🟠"
                                if "Analysis" in name:
                                    icon = "🧠"
                                if "Fix" in name or "Update" in name:
                                    icon = "🛠️"

                                md_lines.append(f"{icon} **{name}**: {det}")
                            timeline_md = "\n\n".join(md_lines)

                    return decision_data, timeline_md
                except Exception as e:
                    return {"error": str(e)}, f"Error reading artifacts: {str(e)}"

            def wrap_healer(file_obj, max_retries):
                """Handle file upload from Gradio and attempt to heal the test file.

                Copies the uploaded file to a local directory, triggers the healing pipeline,
                and retrieves the resulting artifacts.

                Args:
                    file_obj: Gradio file object or string path

                Returns:
                    tuple: (result_text, decision, timeline)
                """
                if file_obj is None:
                    return "Please upload a test file.", None, ""
                try:
                    # In Gradio 6.x, file_count="single" returns a string path directly
                    # Handle both string paths and file objects for compatibility
                    file_path = file_obj if isinstance(file_obj, str) else file_obj.name
                    # Ensure the file is in the project directory so Playwright can find the context
                    local_path = os.path.join(
                        "tests", "generated", os.path.basename(file_path)
                    )
                    # Validate the path before copying
                    validated_path = validation_utils.validate_file_path(local_path)
                    shutil.copy(file_path, validated_path)

                    # 1. Run Healing
                    result_text = attempt_healing(
                        validated_path, max_retries=int(max_retries)
                    )

                    # 2. Fetch Artifacts
                    decision, timeline = get_latest_artifacts()

                    return result_text, decision, timeline
                except ValidationError as e:
                    return f"Validation Error: {str(e)}", None, ""
                except Exception as e:
                    return f"Error: {str(e)}", None, ""

            h_btn.click(
                fn=wrap_healer,
                inputs=[h_file_in, h_max_retries_in],
                outputs=[h_result_out, h_decision_out, h_timeline_out],
            )

if __name__ == "__main__":
    demo.launch(theme=gr.themes.Default(), css=css)
