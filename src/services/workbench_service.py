"""
Workbench service — read-only data access for the AI Engineering Workbench UI.

Surfaces data already produced by the healing pipeline: artifacts, traces,
and benchmark results.  No AI calls are made from this module.

Public API:
    list_artifacts()                -> list[str]     — file paths, newest-first
    load_artifact(path)             -> (str, dict)   — (markdown, raw dict)
    run_classification_benchmark()  -> str           — markdown report
    load_traces()                   -> (str, str)    — (markdown body, summary label)
    get_model_info()                -> str           — markdown table of registered models
"""

from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
_ARTIFACTS_DIR = PROJECT_ROOT / "tests" / "artifacts"
_TRACES_PATH = PROJECT_ROOT / "logs" / "traces.jsonl"
_DATASET_PATH = (
    PROJECT_ROOT / "benchmarks" / "healing" / "fixtures" / "repair_scenarios.json"
)


# ---------------------------------------------------------------------------
# Artifact Inspector
# ---------------------------------------------------------------------------


def list_artifacts() -> list[str]:
    """Return absolute paths to all decision artifacts (healing + generation + vision), newest-first.

    Excludes ``execution_timeline_*.json`` files — those are supplementary to
    healing decisions and are not browsable on their own.

    Returns:
        List of absolute path strings (may be empty if the directory is absent).
    """
    if not _ARTIFACTS_DIR.exists():
        return []
    files = sorted(
        [
            *_ARTIFACTS_DIR.glob("healing_decision_*.json"),
            *_ARTIFACTS_DIR.glob("generation_decision_*.json"),
            *_ARTIFACTS_DIR.glob("vision_decision_*.json"),
        ],
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    return [str(f) for f in files]


def load_artifact(artifact_path: str) -> tuple[str, dict]:
    """Parse a decision artifact and return a human-readable view.

    Dispatches to the correct schema based on the filename prefix:
      ``healing_decision_*``    → HealingDecision
      ``generation_decision_*`` → GenerationDecision
      ``vision_decision_*``     → VisionDecision

    Args:
        artifact_path: Absolute or relative path to a ``*_decision_*.json`` file.

    Returns:
        ``(markdown_report, raw_dict)`` — markdown from the decision's
        ``to_markdown()``; raw_dict is the JSON-parsed content for the JSON panel.
    """
    path = Path(artifact_path)
    if not path.exists():
        return f"*File not found: `{artifact_path}`*", {}

    try:
        raw: dict = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        return f"*Could not read file: {exc}*", {}

    name = path.name
    try:
        if name.startswith("generation_decision_"):
            from schemas.generation import GenerationDecision

            md = GenerationDecision.model_validate(raw).to_markdown()
        elif name.startswith("vision_decision_"):
            from schemas.generation import VisionDecision

            md = VisionDecision.model_validate(raw).to_markdown()
        else:
            # healing_decision_* and any unknown prefix
            from schemas.healing import HealingDecision

            md = HealingDecision.model_validate(raw).to_markdown()
    except Exception as exc:
        logger.warning("Could not parse %s: %s", path.name, exc)
        md = (
            f"*Could not parse `{path.name}`: {exc}*\n\n"
            f"```json\n{json.dumps(raw, indent=2)[:2000]}\n```"
        )

    return md, raw


# ---------------------------------------------------------------------------
# Benchmark Explorer
# ---------------------------------------------------------------------------


def run_classification_benchmark() -> str:
    """Run the heuristic failure-classification benchmark and return a markdown report.

    Uses the healing dataset at ``benchmarks/healing/fixtures/repair_scenarios.json``.
    This is classification-only — no LLM or browser is required.  The benchmark
    is fully deterministic and completes in milliseconds.

    Returns:
        Markdown string suitable for display in a ``gr.Markdown`` component.
    """
    from benchmarks.healing.runner import run_healing_benchmark
    from schemas.evaluation import BenchmarkRunConfig

    if not _DATASET_PATH.exists():
        return (
            "**Dataset not found.**\n\n"
            f"Expected: `{_DATASET_PATH.relative_to(PROJECT_ROOT)}`\n\n"
            "Run `git status` to verify the benchmarks directory is present."
        )

    config = BenchmarkRunConfig(
        model="heuristic-classifier",
        provider="local",
        prompt_name="classify_failure_heuristic",
        prompt_version="1",
        prompt_hash="n/a",
        temperature=0.0,
        dataset_version="1.0.0",
        benchmark_type="healing-classification",
        timestamp=datetime.now().isoformat(),
    )

    try:
        run = run_healing_benchmark(_DATASET_PATH, PROJECT_ROOT, config)
    except Exception as exc:
        logger.exception("Benchmark run failed: %s", exc)
        return f"**Benchmark run failed:** `{exc}`"

    pass_icon = "✅" if run.passed == run.total else "⚠️"
    lines = [
        f"## {pass_icon} Heuristic Classification Benchmark",
        f"**{run.passed}/{run.total} passed** ({run.pass_rate * 100:.0f}%)"
        f" · mean score {run.mean_score:.2f}"
        f" · mean latency {run.mean_duration_ms:.0f} ms",
        "",
        "| Case ID | Expected | Classified | Confidence | Pass |",
        "| --- | --- | --- | --- | --- |",
    ]

    for result in run.results:
        d = result.details
        expected = d.get("expected_type") or "—"
        got = d.get("classified_type") or "—"
        conf_val = d.get("confidence")
        conf = f"{conf_val:.2f}" if isinstance(conf_val, float) else "—"
        icon = "✅" if result.passed else "❌"
        lines.append(
            f"| `{result.example_id}` | `{expected}` | `{got}` | {conf} | {icon} |"
        )

    if run.failed > 0:
        lines += [
            "",
            "### Failed Cases",
            "",
        ]
        for result in run.results:
            if not result.passed:
                d = result.details
                reason = d.get("reason") or result.error or "—"
                lines.append(f"- **`{result.example_id}`** — {reason}")

    lines += [
        "",
        f"*Run at {config.timestamp[:19]}. Dataset: `{_DATASET_PATH.name}`.*",
    ]
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Trace Inspector
# ---------------------------------------------------------------------------

_TRACE_DISPLAY_LIMIT = 100  # max spans per type shown in the UI


def load_traces() -> tuple[str, str]:
    """Read ``logs/traces.jsonl`` and return formatted tables.

    Returns:
        ``(markdown_body, summary_label)`` where *markdown_body* is a full
        Markdown string with one table per span type and *summary_label* is a
        short one-line stat for a Gradio label component.
    """
    if not _TRACES_PATH.exists():
        return (
            "*No trace file found at `logs/traces.jsonl`.*\n\n"
            "Run a healing session to generate traces.",
            "0 spans",
        )

    spans: list[dict] = []
    try:
        for line in _TRACES_PATH.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line:
                try:
                    spans.append(json.loads(line))
                except json.JSONDecodeError:
                    pass
    except Exception as exc:
        return f"*Could not read traces: {exc}*", "error"

    if not spans:
        return "*Trace file exists but contains no spans.*", "0 spans"

    sessions = [s for s in spans if s.get("span_type") == "session"]
    llm_spans = [s for s in spans if s.get("span_type") == "llm"]
    sub_spans = [s for s in spans if s.get("span_type") == "subprocess"]

    summary_label = (
        f"{len(spans)} spans — "
        f"{len(sessions)} sessions · "
        f"{len(llm_spans)} LLM calls · "
        f"{len(sub_spans)} subprocess calls"
    )

    lines: list[str] = [
        f"## Trace Explorer — {len(spans)} spans",
        f"*`{_TRACES_PATH.relative_to(PROJECT_ROOT)}`*",
        "",
    ]

    # ── Sessions ────────────────────────────────────────────────────────────
    if sessions:
        lines += [
            f"### Sessions ({len(sessions)})",
            "",
            "| Trace ID | Type | LLM calls | Subprocess calls | Total tokens | Latency ms | Success |",
            "| --- | --- | --- | --- | --- | --- | --- |",
        ]
        for s in sessions[-_TRACE_DISPLAY_LIMIT:]:
            tid = s.get("trace_id", "")[:8]
            stype = s.get("session_type", "—")
            llm_ct = s.get("llm_call_count", 0)
            sub_ct = s.get("subprocess_call_count", 0)
            tok_in = s.get("total_input_tokens", 0)
            tok_out = s.get("total_output_tokens", 0)
            lat = s.get("total_latency_ms", 0)
            ok = "✅" if s.get("success") else "❌"
            lines.append(
                f"| `{tid}…` | {stype} | {llm_ct} | {sub_ct}"
                f" | {tok_in + tok_out:,} | {lat:,} | {ok} |"
            )
        lines.append("")

    # ── LLM spans ───────────────────────────────────────────────────────────
    if llm_spans:
        lines += [
            f"### LLM Calls ({len(llm_spans)})",
            "",
            "| Trace ID | Model | Prompt ver | In tokens | Out tokens | Latency ms | Retries |",
            "| --- | --- | --- | --- | --- | --- | --- |",
        ]
        for s in llm_spans[-_TRACE_DISPLAY_LIMIT:]:
            tid = s.get("trace_id", "")[:8]
            model = s.get("model", "—")
            pver = s.get("prompt_version") or "—"
            tok_in = s.get("input_tokens", 0)
            tok_out = s.get("output_tokens", 0)
            lat = s.get("latency_ms", 0)
            retries = s.get("retry_count", 0)
            lines.append(
                f"| `{tid}…` | {model} | {pver}"
                f" | {tok_in:,} | {tok_out:,} | {lat:,} | {retries} |"
            )
        lines.append("")

    # ── Subprocess spans ─────────────────────────────────────────────────────
    if sub_spans:
        lines += [
            f"### Subprocess Calls ({len(sub_spans)})",
            "",
            "| Trace ID | Command | Exit code | Latency ms | Success |",
            "| --- | --- | --- | --- | --- |",
        ]
        for s in sub_spans[-_TRACE_DISPLAY_LIMIT:]:
            tid = s.get("trace_id", "")[:8]
            cmd = (s.get("command") or "—")[:60]
            exit_code = s.get("exit_code", "—")
            lat = s.get("latency_ms", 0)
            ok = "✅" if s.get("success") else "❌"
            lines.append(f"| `{tid}…` | `{cmd}` | {exit_code} | {lat:,} | {ok} |")
        lines.append("")

    lines.append(f"*Showing up to {_TRACE_DISPLAY_LIMIT} most recent spans per type.*")
    return "\n".join(lines), summary_label


# ---------------------------------------------------------------------------
# Model Registry
# ---------------------------------------------------------------------------


def get_model_info() -> str:
    """Return a markdown table of all models registered in ModelRegistry.

    Reads the environment variables (``LM_STUDIO_MODEL``, ``OLLAMA_MODEL``, etc.)
    and populates ModelRegistry.  Safe to call repeatedly — each call re-reads
    the environment so live config changes are reflected on refresh.

    Returns:
        Markdown string with one row per registered model.
    """
    from src.llm.registry import ModelRegistry

    # Re-populate from env each time so the panel reflects current config.
    ModelRegistry.clear()
    ModelRegistry.from_env()
    models = ModelRegistry.all_models()

    if not models:
        return (
            "## Model Registry\n\n"
            "*No models registered. Check that `LM_STUDIO_MODEL` / "
            "`OLLAMA_MODEL` environment variables are set.*"
        )

    lines = [
        "## Model Registry",
        "",
        "Populated from environment variables at startup.  "
        "Click **Refresh** to re-read after changing `.env`.",
        "",
        "| Model ID | Provider | Vision | Context Window | Description |",
        "| --- | --- | --- | --- | --- |",
    ]
    for m in models:
        vision_icon = "✅" if m.is_vision_capable else "—"
        lines.append(
            f"| `{m.model_id}` | {m.provider} | {vision_icon}"
            f" | {m.context_window:,} | {m.description} |"
        )

    lines += [
        "",
        f"*{len(models)} model(s) registered.*",
    ]
    return "\n".join(lines)
