"""
AI Engineering Workbench — Gradio interface.

UI wiring only.  All pipeline logic lives in src/services/.
All inspector/benchmark logic lives in src/services/workbench_service.py.

Tabs:
  Generation Pipeline  generate_test_streaming + run_test_streaming
  Healing Pipeline     heal_test_streaming
  Vision Pipeline      analyze_visual_streaming + run_vision_test_streaming
  Artifact Inspector   browse tests/artifacts/ healing decisions
  Benchmark Explorer   run heuristic classification benchmark (no LLM)
  Trace Inspector      browse logs/traces.jsonl
"""

import logging
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.append(str(PROJECT_ROOT))

import gradio as gr

from src.observability import configure_tracer

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)

# Activate the JSONL tracer so every pipeline run writes spans to logs/traces.jsonl.
configure_tracer()

from src.services.generation_service import generate_test_streaming, run_test_streaming
from src.services.healing_service import heal_test_streaming
from src.services.vision_service import (
    analyze_visual_streaming,
    run_vision_test_streaming,
)
from src.services.workbench_service import (
    list_artifacts,
    load_artifact,
    load_traces,
    run_classification_benchmark,
)

css = """
.tall-textbox textarea { min-height: 300px !important; }
.tall-code .code-container { min-height: 400px !important; }
.tall-md { min-height: 400px; }
h1 {
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
    font-weight: 600;
    letter-spacing: -0.025em;
}
.gradio-container {
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
}
"""

# ---------------------------------------------------------------------------
# Artifact Inspector helpers (thin wrappers that satisfy Gradio's event model)
# ---------------------------------------------------------------------------


def refresh_artifacts() -> gr.Dropdown:
    """Return an updated Dropdown populated with the current artifact list."""
    paths = list_artifacts()
    choices = [Path(p).name for p in paths]
    value = choices[0] if choices else None
    return gr.Dropdown(choices=choices, value=value)


def _name_to_path(name: str) -> str:
    """Resolve a bare filename back to an absolute path under tests/artifacts/."""
    return str(PROJECT_ROOT / "tests" / "artifacts" / name)


def on_artifact_select(name: str) -> tuple[str, dict]:
    """Load a healing artifact by its basename."""
    if not name:
        return "*Select an artifact from the dropdown.*", {}
    return load_artifact(_name_to_path(name))


# ---------------------------------------------------------------------------
# UI
# ---------------------------------------------------------------------------

with gr.Blocks(title="AI Engineering Workbench", css=css) as demo:
    gr.Markdown("# AI Engineering Workbench")
    gr.Markdown(
        "Reference implementation: structured LLM outputs · "
        "evaluation · observability · AST-based repair · explainability"
    )

    with gr.Tabs():
        # ── Tab 1: Generation Pipeline ──────────────────────────────────────
        with gr.Tab("Generation Pipeline"):
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
                    gen_timeline = gr.Markdown("### Generation Timeline\n*Ready.*")

                with gr.Column(scale=5):
                    with gr.Tabs():
                        with gr.Tab("Generated Code"):
                            code_out = gr.Code(
                                label="TypeScript",
                                language="typescript",
                                lines=20,
                                elem_classes=["tall-code"],
                            )
                        with gr.Tab("Execution Logs"):
                            result_out = gr.Textbox(
                                label="Execution Log",
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

        # ── Tab 2: Healing Pipeline ─────────────────────────────────────────
        with gr.Tab("Healing Pipeline"):
            with gr.Row():
                with gr.Column(scale=3):
                    h_file_in = gr.File(
                        label="Test File (.ts)",
                        file_types=[".ts"],
                        file_count="single",
                    )
                    h_max_retries_in = gr.Slider(
                        minimum=1,
                        maximum=5,
                        value=3,
                        step=1,
                        label="Max Repair Attempts",
                    )
                    h_btn = gr.Button("Run Healing Pipeline", variant="primary")

                with gr.Column(scale=4):
                    h_timeline_out = gr.Markdown(
                        "### Healing Timeline\n*Upload a test file and run.*"
                    )

                with gr.Column(scale=5):
                    with gr.Tabs():
                        with gr.Tab("Decision Report"):
                            h_explanation_out = gr.Markdown(
                                "### Healing Decision\n*No run active.*",
                                elem_classes=["tall-md"],
                            )
                        with gr.Tab("Execution Logs"):
                            h_result_out = gr.Textbox(
                                label="Execution Log",
                                interactive=False,
                                lines=20,
                                elem_classes=["tall-textbox"],
                            )
                        with gr.Tab("Raw JSON"):
                            with gr.Accordion("HealingDecision JSON", open=False):
                                h_decision_out = gr.JSON(label="Raw artifact")

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

        # ── Tab 3: Vision Pipeline ──────────────────────────────────────────
        with gr.Tab("Vision Pipeline"):
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
                        "### Vision Timeline\n*Ready to capture screenshot.*"
                    )

                with gr.Column(scale=5):
                    with gr.Tabs():
                        with gr.Tab("Screenshot"):
                            v_image_preview = gr.Image(
                                label="Captured Screenshot",
                                type="filepath",
                                interactive=False,
                            )
                        with gr.Tab("Generated Code"):
                            v_code_out = gr.Code(
                                label="TypeScript",
                                language="typescript",
                                lines=20,
                                elem_classes=["tall-code"],
                            )
                        with gr.Tab("Execution Logs"):
                            v_result_out = gr.Textbox(
                                label="Execution Log",
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

        # ── Tab 4: Artifact Inspector ───────────────────────────────────────
        with gr.Tab("Artifact Inspector"):
            gr.Markdown(
                "Browse decision artifacts written to `tests/artifacts/` by every pipeline run "
                "(healing, generation, vision). Each artifact carries full provenance: model, "
                "provider, prompt version, token counts, latency, and trace ID."
            )
            with gr.Row():
                artifact_dropdown = gr.Dropdown(
                    label="Decision Artifact",
                    choices=[],
                    value=None,
                    interactive=True,
                    scale=5,
                )
                artifact_refresh_btn = gr.Button("Refresh", scale=1)

            with gr.Row():
                with gr.Column(scale=3):
                    artifact_md = gr.Markdown(
                        "*Select an artifact above.*",
                        elem_classes=["tall-md"],
                    )
                with gr.Column(scale=2):
                    artifact_json = gr.JSON(label="Raw JSON")

            artifact_refresh_btn.click(
                fn=refresh_artifacts,
                inputs=[],
                outputs=[artifact_dropdown],
            )
            artifact_dropdown.change(
                fn=on_artifact_select,
                inputs=[artifact_dropdown],
                outputs=[artifact_md, artifact_json],
            )

        # ── Tab 5: Benchmark Explorer ───────────────────────────────────────
        with gr.Tab("Benchmark Explorer"):
            gr.Markdown(
                "Run the heuristic failure-classification benchmark against the "
                "`benchmarks/healing/fixtures/repair_scenarios.json` dataset. "
                "No LLM or browser required — fully deterministic, completes in milliseconds."
            )
            benchmark_run_btn = gr.Button(
                "Run Heuristic Classification Benchmark", variant="primary"
            )
            benchmark_out = gr.Markdown("*Click the button to run the benchmark.*")

            benchmark_run_btn.click(
                fn=run_classification_benchmark,
                inputs=[],
                outputs=[benchmark_out],
            )

        # ── Tab 6: Trace Inspector ──────────────────────────────────────────
        with gr.Tab("Trace Inspector"):
            gr.Markdown(
                "Inspect JSONL traces written to `logs/traces.jsonl` by the observability "
                "layer.  Each healing session produces session, LLM, and subprocess spans "
                "linked by `trace_id`."
            )
            with gr.Row():
                trace_load_btn = gr.Button("Load Traces", variant="primary")
                trace_summary = gr.Label(label="Summary", value="—")

            trace_out = gr.Markdown("*Click Load Traces to read `logs/traces.jsonl`.*")

            def _load_traces_handler() -> tuple[str, str]:
                body, label = load_traces()
                return body, label

            trace_load_btn.click(
                fn=_load_traces_handler,
                inputs=[],
                outputs=[trace_out, trace_summary],
            )

if __name__ == "__main__":
    demo.launch(theme=gr.themes.Default(), css=css)
