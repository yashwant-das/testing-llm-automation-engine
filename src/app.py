"""
Gradio web interface for the Testing LLM Automation Engine.

UI wiring only — all orchestration logic lives in src/services/.

Tabs:
  Test Generator  generate_test_streaming + run_test_streaming
  Vision Agent    analyze_visual_streaming + run_vision_test_streaming
  Self-Healer     heal_test_streaming
"""

import logging
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.append(str(PROJECT_ROOT))

import gradio as gr

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)

from src.services.generation_service import generate_test_streaming, run_test_streaming
from src.services.healing_service import heal_test_streaming
from src.services.vision_service import (
    analyze_visual_streaming,
    run_vision_test_streaming,
)

css = """
.tall-textbox textarea { min-height: 300px !important; }
.tall-code .code-container { min-height: 400px !important; }
h1 {
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
    font-weight: 600;
    letter-spacing: -0.025em;
}
.gradio-container {
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
}
"""

with gr.Blocks(title="Testing LLM Automation Engine") as demo:
    gr.Markdown("# Testing LLM Automation Engine")
    gr.Markdown("Generate, test, and maintain Playwright test automation scripts.")

    with gr.Tabs():
        with gr.Tab("Test Generator"):  # ── Tab 1: Test Generator ──────────
            with gr.Row():
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

                with gr.Column(scale=4):
                    gen_timeline = gr.Markdown(
                        "### ⏱️ Generation Timeline\n*Ready to generate...*"
                    )

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

            gen_btn.click(
                fn=generate_test_streaming,
                inputs=[url_in, story_in],
                outputs=[gen_timeline, code_out],
            )
            run_btn.click(
                fn=run_test_streaming,
                inputs=[url_in, code_out, story_in],
                outputs=[gen_timeline, result_out],
            )

        with gr.Tab("Vision Agent"):  # ── Tab 2: Vision Agent ──────────────
            with gr.Row():
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

                with gr.Column(scale=4):
                    v_timeline = gr.Markdown(
                        "### ⏱️ Visual Timeline\n*Ready to capture screenshot...*"
                    )

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

            v_btn.click(
                fn=analyze_visual_streaming,
                inputs=[v_url_in, v_story_in],
                outputs=[v_timeline, v_image_preview, v_code_out],
            )
            v_run_btn.click(
                fn=run_vision_test_streaming,
                inputs=[v_url_in, v_code_out, v_story_in],
                outputs=[v_timeline, v_result_out],
            )

        with gr.Tab("Self-Healer"):  # ── Tab 3: Self-Healer ───────────────
            with gr.Row():
                with gr.Column(scale=3):
                    h_file_in = gr.File(
                        label="Test File",
                        file_types=[".ts"],
                        file_count="single",
                    )
                    h_max_retries_in = gr.Slider(
                        minimum=1,
                        maximum=5,
                        value=3,
                        step=1,
                        label="Max Healing Attempts",
                    )
                    h_btn = gr.Button("Heal Test", variant="primary")

                with gr.Column(scale=4):
                    h_timeline_out = gr.Markdown(
                        "### ⏱️ Healing Process Timeline\n*Ready to load spec and heal...*"
                    )

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

            h_btn.click(
                fn=heal_test_streaming,
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
