"""
AI Engineering Workbench — Gradio interface.

UI wiring only.  All pipeline logic lives in src/services/.
All inspector/benchmark logic lives in src/services/workbench_service.py.

Tab groups (Phase 17 Stage 5 — Information Architecture):

  Tab 1: Overview           — system description, pipeline topology, Recent Runs
  ─── Pipelines ──────────────────────────────────────────────────────────────
  Tab 2: Generation         generate_test_streaming + run_test_streaming
  Tab 3: Healing            heal_test_streaming (IA-4: auto-populates inspector)
  Tab 4: Vision             analyze_visual_streaming + run_vision_test_streaming
  ─── Engineering ─────────────────────────────────────────────────────────────
  Tab 5: Artifact Inspector browse all decision artifacts
  Tab 6: Evaluation         heuristic + LLM benchmarks, run history
  Tab 7: Trace Inspector    browse logs/traces.jsonl
  Tab 8: Models             registered model capabilities
"""

import logging
import sys
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.append(str(PROJECT_ROOT))

load_dotenv(PROJECT_ROOT / ".env")

import gradio as gr

from src.observability import configure_tracer
from src.utils.logger import init_logging

init_logging()
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
    get_model_info,
    get_system_overview,
    list_artifacts,
    load_artifact,
    load_benchmark_history,
    load_most_recent_artifact,
    load_run_history,
    load_traces,
    run_classification_benchmark,
    run_generation_benchmark_ui,
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

with gr.Blocks(title="AI Engineering Workbench") as demo:
    gr.Markdown("# AI Engineering Workbench")
    gr.Markdown(
        "Reference implementation: structured LLM outputs · "
        "evaluation · observability · AST-based repair · explainability"
    )

    with gr.Tabs():
        # ── Tab 1: Overview ─────────────────────────────────────────────────
        with gr.Tab("Overview"):
            gr.Markdown(get_system_overview())
            gr.Markdown("---")
            with gr.Row():
                run_history_refresh_btn = gr.Button("Refresh Recent Runs", scale=1)
                with gr.Column(scale=5):
                    gr.Markdown(
                        "Cross-pipeline timeline — one row per decision artifact."
                    )
            run_history_out = gr.Markdown(
                "*Click **Refresh Recent Runs** to load the unified run history.*"
            )
            run_history_refresh_btn.click(
                fn=load_run_history,
                inputs=[],
                outputs=[run_history_out],
            )

        # ── Tab 2: Generation Pipeline ──────────────────────────────────────
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
                        value="TC-AUTH-001: Verify that a registered user can authenticate using valid credentials and is redirected to the secure area.",
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

        # ── Tab 3: Healing Pipeline ─────────────────────────────────────────
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
                                "### Healing Decision\n*No run active.*\n\n"
                                "*After a run, this report is also available in the "
                                "**Artifact Inspector** tab with the same content.*",
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

        # ── Tab 4: Vision Pipeline ──────────────────────────────────────────
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
                        value="TC-AUTH-001: Verify that standard_user can log in with valid credentials and land on the product inventory page.",
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
                        with gr.Tab("Generated Code"):
                            v_code_out = gr.Code(
                                label="TypeScript",
                                language="typescript",
                                lines=20,
                                elem_classes=["tall-code"],
                            )
                        with gr.Tab("Screenshot"):
                            v_image_preview = gr.Image(
                                label="Captured Screenshot",
                                type="filepath",
                                interactive=False,
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

        # ── Tab 5: Artifact Inspector ───────────────────────────────────────
        with gr.Tab("Artifact Inspector"):
            gr.Markdown(
                "Browse decision artifacts written to `tests/artifacts/` by every pipeline run "
                "(healing, generation, vision). Each artifact carries full provenance: model, "
                "provider, prompt version, token counts, latency, and trace ID.\n\n"
                "After a **Healing Pipeline** run the inspector auto-loads the new artifact "
                "— no manual Refresh needed."
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

        # ── Tab 6: Evaluation ──────────────────────────────────────────────
        with gr.Tab("Evaluation"):
            gr.Markdown(
                "Run benchmarks and compare results across runs.  "
                "Reports are saved to `benchmarks/reports/` so every run "
                "is tracked for regression detection."
            )

            with gr.Tabs():
                # ── Heuristic classification ────────────────────────────────
                with gr.Tab("Heuristic Classification"):
                    gr.Markdown(
                        "Runs the failure-classification heuristic against "
                        "`benchmarks/healing/fixtures/repair_scenarios.json`. "
                        "No LLM or browser required — fully deterministic, "
                        "completes in milliseconds.  Results are saved to "
                        "`benchmarks/reports/` and reflected in **Run History**."
                    )
                    benchmark_run_btn = gr.Button(
                        "Run Heuristic Classification Benchmark", variant="primary"
                    )
                    benchmark_out = gr.Markdown(
                        "*Click the button to run the benchmark.*"
                    )

                    def _run_classification_and_refresh():
                        result = run_classification_benchmark()
                        history = load_benchmark_history()
                        return result, history

                    benchmark_run_btn.click(
                        fn=_run_classification_and_refresh,
                        inputs=[],
                        outputs=[benchmark_out, gr.Markdown(visible=False)],
                    )

                # ── Generation benchmark (LLM-backed) ──────────────────────
                with gr.Tab("Generation (LLM)"):
                    gr.Markdown(
                        "Runs the generation benchmark against "
                        "`benchmarks/generation/fixtures/web_scenarios.json`. "
                        "**Requires a local LLM** — the button checks availability "
                        "first and shows a clear error if the model is not reachable."
                    )
                    gen_bench_btn = gr.Button(
                        "Run Generation Benchmark", variant="primary"
                    )
                    gen_bench_out = gr.Markdown(
                        "*Click the button to run. LLM must be running.*"
                    )

                    gen_bench_btn.click(
                        fn=run_generation_benchmark_ui,
                        inputs=[],
                        outputs=[gen_bench_out],
                    )

            # ── Run history (shared across benchmark types) ─────────────────
            gr.Markdown("---")
            with gr.Row():
                history_refresh_btn = gr.Button("Refresh History", scale=1)
                with gr.Column(scale=5):
                    gr.Markdown("Run-over-run comparison from `benchmarks/reports/`.")
            history_out = gr.Markdown(
                "*Click Refresh History or run a benchmark above.*"
            )

            history_refresh_btn.click(
                fn=load_benchmark_history,
                inputs=[],
                outputs=[history_out],
            )

        # ── Tab 7: Trace Inspector ──────────────────────────────────────────
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

        # ── Tab 8: Models ──────────────────────────────────────────────────
        with gr.Tab("Models"):
            gr.Markdown(
                "Active models read from environment variables "
                "(`LM_STUDIO_TEXT_MODEL`, `LM_STUDIO_VISION_MODEL`, "
                "`OLLAMA_TEXT_MODEL`, `OLLAMA_VISION_MODEL`).  "
                "Shows capability metadata registered in `ModelRegistry`."
            )
            with gr.Row():
                models_refresh_btn = gr.Button("Refresh", variant="primary")
            models_out = gr.Markdown("*Click Refresh to load model registry.*")

            models_refresh_btn.click(
                fn=get_model_info,
                inputs=[],
                outputs=[models_out],
            )

    # ── IA-4: Healing run auto-populates Artifact Inspector ─────────────────
    # Wire healing button *after* all tab components are defined so that
    # artifact_dropdown, artifact_md, and artifact_json are in scope.
    h_btn.click(
        fn=heal_test_streaming,
        inputs=[h_file_in, h_max_retries_in],
        outputs=[
            h_result_out,
            h_explanation_out,
            h_timeline_out,
            h_decision_out,
        ],
    ).then(
        fn=refresh_artifacts,
        inputs=[],
        outputs=[artifact_dropdown],
    ).then(
        fn=load_most_recent_artifact,
        inputs=[],
        outputs=[artifact_md, artifact_json],
    )

if __name__ == "__main__":
    demo.launch(
        theme=gr.themes.Default(),
        css=css,
        allowed_paths=[str(PROJECT_ROOT / "tests" / "screenshots")],
    )
