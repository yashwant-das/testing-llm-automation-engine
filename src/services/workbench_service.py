"""
Workbench service — read-only data access for the AI Engineering Workbench UI.

Surfaces data already produced by the healing pipeline: artifacts, traces,
and benchmark results.  No AI calls are made from this module.

Public API:
    list_artifacts()                -> list[str]     — file paths, newest-first
    load_artifact(path)             -> (str, dict)   — (markdown, raw dict)
    load_most_recent_artifact()     -> (str, dict)   — newest artifact (IA-4 auto-populate)
    load_run_history(limit)         -> str           — unified cross-pipeline run table
    get_system_overview()           -> str           — static system description markdown
    run_classification_benchmark()  -> str           — markdown report (saves to benchmarks/reports/)
    load_benchmark_history()        -> str           — markdown delta table from saved reports
    check_llm_available()           -> (bool, str)   — LLM reachability probe
    run_generation_benchmark_ui()   -> str           — LLM-guarded generation benchmark
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
_GEN_DATASET_PATH = (
    PROJECT_ROOT / "benchmarks" / "generation" / "fixtures" / "web_scenarios.json"
)
_REPORTS_DIR = PROJECT_ROOT / "benchmarks" / "reports"


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
# Information architecture helpers (Stage 5)
# ---------------------------------------------------------------------------

_RUN_HISTORY_LIMIT = 20  # max runs shown in the unified history table

#: Static markdown describing the system — rendered in the Overview tab.
_SYSTEM_OVERVIEW_MD = """\
## What is this?

The **AI Engineering Workbench** is a reference implementation for production-grade
AI-assisted test automation. It demonstrates how to build LLM-powered pipelines that
are observable, evaluable, and self-healing — using local models (LM Studio / Ollama)
with no cloud dependency.

## Pipeline topology

```text
URL + scenario
    │
    ▼
Generation Pipeline ──▶ Playwright test file
    │
    ▼ (test fails)
Healing Pipeline ───────▶ LLM + AST repair ──▶ repaired test
    │
    ▼ (screenshot path)
Vision Pipeline ────────▶ vision LLM ─────────▶ test from screenshot
    │
    All three pipelines write decision artifacts to tests/artifacts/
    └── Artifact Inspector · Run History · Evaluation · Trace Inspector
```

## Navigation guide

**Pipelines** — LLM-backed authoring surfaces (tabs 2–4):

- **Generation Pipeline** — give a URL and scenario, get a Playwright test
- **Healing Pipeline** — give a failing test, get an LLM-repaired version
- **Vision Pipeline** — give a URL, get a test generated from a screenshot

**Engineering** — observability and quality surfaces (tabs 5–8):

- **Artifact Inspector** — browse every decision artifact with full provenance
- **Run History** — unified cross-pipeline timeline, one row per artifact
- **Evaluation** — run repeatable benchmarks and track pass-rate over time
- **Trace Inspector** — inspect OpenTelemetry spans from every session
- **Models** — see which LLM models are registered and their capabilities
"""


def get_system_overview() -> str:
    """Return static system overview markdown for the Overview tab.

    Returns:
        Markdown string describing the system, pipeline topology, and navigation.
    """
    return _SYSTEM_OVERVIEW_MD


def _pipeline_label(filename: str) -> str:
    """Infer a human-readable pipeline name from an artifact filename."""
    if filename.startswith("healing_decision"):
        return "Healing"
    if filename.startswith("generation_decision"):
        return "Generation"
    if filename.startswith("vision_decision"):
        return "Vision"
    return "Unknown"


def _run_status(data: dict, pipeline: str) -> str:
    """Infer a status badge from artifact data."""
    if pipeline == "Healing":
        passed = data.get("verification_passed")
        if passed is True:
            return "✅ Healed"
        if passed is False:
            return "❌ Failed"
        return "—"
    return "✅ Done"


def load_run_history(limit: int = _RUN_HISTORY_LIMIT) -> str:
    """Return a unified cross-pipeline run history table.

    Reads all decision artifacts from ``tests/artifacts/`` (healing, generation,
    and vision), sorts them newest-first, and renders a markdown table with one
    row per run.  This is the "Unified Run History" surface (Phase 17 Opportunity 7).

    Args:
        limit: Maximum number of rows to show (default 20).

    Returns:
        Markdown string with a run table, or a placeholder if no artifacts exist.
    """
    if not _ARTIFACTS_DIR.exists():
        return (
            "## Recent Runs\n\n"
            "*Artifacts directory not found. Run a pipeline to create the first artifact.*"
        )

    patterns = [
        "healing_decision_*.json",
        "generation_decision_*.json",
        "vision_decision_*.json",
    ]
    files: list[Path] = []
    for pat in patterns:
        files.extend(_ARTIFACTS_DIR.glob(pat))

    if not files:
        return (
            "## Recent Runs\n\n"
            "*No decision artifacts found yet. Run a pipeline to see results here.*"
        )

    files.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    files = files[:limit]

    rows: list[tuple[str, str, str, str, str, str]] = []
    for path in files:
        try:
            data: dict = json.loads(path.read_text(encoding="utf-8"))
        except Exception as exc:
            logger.warning("Could not read artifact %s: %s", path.name, exc)
            continue

        pipeline = _pipeline_label(path.name)
        timestamp = (data.get("timestamp") or "")[:19] or "—"
        model = data.get("model_used") or "—"
        trace_id = data.get("trace_id") or ""
        status = _run_status(data, pipeline)
        trace_str = f"`{trace_id[:8]}…`" if trace_id else "—"
        rows.append((timestamp, pipeline, model, status, path.name, trace_str))

    if not rows:
        return "## Recent Runs\n\n*No valid artifacts found.*"

    lines = [
        "## Recent Runs",
        "",
        f"Showing {len(rows)} most recent run(s) across all pipelines — newest first.",
        "",
        "| Timestamp | Pipeline | Model | Status | Artifact | Trace |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for timestamp, pipeline, model, status, artifact, trace_str in rows:
        lines.append(
            f"| {timestamp} | {pipeline} | {model} | {status} | `{artifact}` | {trace_str} |"
        )
    lines += ["", f"*Updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*"]
    return "\n".join(lines)


def load_most_recent_artifact() -> tuple[str, dict]:
    """Load the most recently written decision artifact.

    Used by the IA-4 auto-populate: after a pipeline run completes, the
    Artifact Inspector auto-loads the new artifact without a manual Refresh.

    Returns:
        ``(markdown_report, raw_dict)`` in the same format as :func:`load_artifact`.
        Returns a placeholder tuple if no artifacts exist.
    """
    paths = list_artifacts()
    if not paths:
        return (
            "*No artifacts found yet. Run a pipeline to create the first artifact.*",
            {},
        )
    return load_artifact(paths[0])


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

    # Persist the report so history comparison works.
    try:
        report_path = run.save_report(_REPORTS_DIR)
        logger.info("Benchmark report saved: %s", report_path)
    except Exception as exc:
        logger.warning("Could not save benchmark report: %s", exc)
        report_path = None

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

    saved_note = (
        f"`{report_path.name}`" if report_path else "*(report could not be saved)*"
    )
    lines += [
        "",
        f"*Run at {config.timestamp[:19]}. Dataset: `{_DATASET_PATH.name}`."
        f" Report: {saved_note}.*",
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
# Benchmark history
# ---------------------------------------------------------------------------

_HISTORY_DISPLAY_LIMIT = 10  # max runs shown in the history table


def load_benchmark_history() -> str:
    """Load all saved benchmark reports and return a markdown comparison table.

    Reads ``benchmarks/reports/*.json`` (all benchmark types), sorts them newest-first,
    and shows a run-over-run delta on pass rate, mean score, and mean latency.

    Returns:
        Markdown string with a history table and delta column.
    """
    if not _REPORTS_DIR.exists():
        return (
            "## Benchmark History\n\n"
            "*No reports saved yet. Run a benchmark to record the first baseline.*"
        )

    report_files = sorted(
        _REPORTS_DIR.glob("*.json"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )

    if not report_files:
        return (
            "## Benchmark History\n\n"
            "*No reports found in `benchmarks/reports/`. "
            "Run a benchmark to record the first baseline.*"
        )

    runs: list[tuple[str, float, float, float]] = []  # (label, pass_rate, score, lat)
    for path in report_files[:_HISTORY_DISPLAY_LIMIT]:
        try:
            from schemas.evaluation import BenchmarkRun

            run = BenchmarkRun.model_validate_json(path.read_text(encoding="utf-8"))
            label = f"{run.config.benchmark_type} / {run.config.model}"
            runs.append((label, run.pass_rate, run.mean_score, run.mean_duration_ms))
        except Exception as exc:
            logger.warning("Could not parse report %s: %s", path.name, exc)

    if not runs:
        return "## Benchmark History\n\n*All report files failed to parse.*"

    lines = [
        "## Benchmark History",
        f"*{len(runs)} run(s) — newest first · up to {_HISTORY_DISPLAY_LIMIT} shown*",
        "",
        "| Run | Pass rate | Δ pass | Mean score | Δ score | Mean latency ms |",
        "| --- | --- | --- | --- | --- | --- |",
    ]

    for i, (label, pr, sc, lat) in enumerate(runs):
        if i + 1 < len(runs):
            prev_pr, prev_sc = runs[i + 1][1], runs[i + 1][2]
            delta_pr = pr - prev_pr
            delta_sc = sc - prev_sc
            delta_pr_str = f"{delta_pr:+.1%}"
            delta_sc_str = f"{delta_sc:+.3f}"
        else:
            delta_pr_str = "*(baseline)*"
            delta_sc_str = "*(baseline)*"

        lines.append(
            f"| {label} | {pr:.1%} | {delta_pr_str}"
            f" | {sc:.3f} | {delta_sc_str} | {lat:.0f} |"
        )

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# LLM availability check
# ---------------------------------------------------------------------------


def check_llm_available() -> tuple[bool, str]:
    """Check whether the primary LLM is reachable.

    Makes a minimal completion call (1 token) to the primary model.
    Used to gate LLM-backed benchmarks so the UI shows a clear error
    instead of a long timeout.

    Returns:
        ``(available, message)`` — if ``available`` is False, ``message``
        describes why.
    """
    try:
        from src.llm import get_default_router

        router = get_default_router()
        router.complete_primary(
            messages=[{"role": "user", "content": "ping"}],
            temperature=0.0,
            max_tokens=1,
        )
        return True, "LLM reachable"
    except Exception as exc:
        return False, f"LLM not reachable: {exc}"


# ---------------------------------------------------------------------------
# Generation benchmark (LLM-backed)
# ---------------------------------------------------------------------------


def run_generation_benchmark_ui(model_id: str = "") -> str:
    """Run the generation benchmark against the real generator, with an LLM guard.

    Checks LLM availability first; returns a clear error message if the model is
    not reachable rather than timing out silently.  On success, saves the report
    to ``benchmarks/reports/`` and returns a markdown summary.

    Args:
        model_id: Hint for display purposes — the model displayed in the report
                  config comes from the live router (env vars).

    Returns:
        Markdown string suitable for display in a ``gr.Markdown`` component.
    """
    available, msg = check_llm_available()
    if not available:
        return (
            "## Generation Benchmark — LLM Unavailable\n\n"
            f"❌ {msg}\n\n"
            "Check that your local LLM server (LM Studio / Ollama) is running "
            "and the `LM_STUDIO_BASE_URL` / `OLLAMA_BASE_URL` environment variables "
            "are set correctly, then click **Run Generation Benchmark** again."
        )

    if not _GEN_DATASET_PATH.exists():
        try:
            rel = _GEN_DATASET_PATH.relative_to(PROJECT_ROOT)
        except ValueError:
            rel = _GEN_DATASET_PATH
        return f"**Generation dataset not found.**\n\nExpected: `{rel}`"

    from benchmarks.generation.runner import run_generation_benchmark
    from schemas.evaluation import BenchmarkRunConfig
    from src.llm import get_default_router
    from src.utils.prompt_loader import get_prompt_hash, get_prompt_version

    router = get_default_router()
    config = BenchmarkRunConfig(
        model=model_id or router.primary_model,
        provider="local",
        prompt_name="generator",
        prompt_version=get_prompt_version("generator"),
        prompt_hash=get_prompt_hash("generator"),
        temperature=0.1,
        dataset_version="1.0.0",
        benchmark_type="generation",
        timestamp=datetime.now().isoformat(),
    )

    def _generator_fn(url: str, feature_description: str) -> str:
        from src.agents.generator import generate_test_script

        try:
            decision = generate_test_script(url, feature_description)
            return decision.code
        except Exception as exc:
            return f"Error: {exc}"

    try:
        run = run_generation_benchmark(_GEN_DATASET_PATH, _generator_fn, config)
    except Exception as exc:
        logger.exception("Generation benchmark failed: %s", exc)
        return f"**Generation benchmark failed:** `{exc}`"

    try:
        report_path = run.save_report(_REPORTS_DIR)
    except Exception as exc:
        logger.warning("Could not save generation benchmark report: %s", exc)
        report_path = None

    pass_icon = "✅" if run.passed == run.total else "⚠️"
    lines = [
        f"## {pass_icon} Generation Benchmark",
        f"**{run.passed}/{run.total} passed** ({run.pass_rate * 100:.0f}%)"
        f" · mean score {run.mean_score:.2f}"
        f" · mean latency {run.mean_duration_ms:.0f} ms"
        f" · model `{config.model}`",
        "",
        "| Scenario | Score | Pass |",
        "| --- | --- | --- |",
    ]
    for result in run.results:
        icon = "✅" if result.passed else "❌"
        lines.append(f"| `{result.example_id}` | {result.score:.2f} | {icon} |")

    saved_note = (
        f"`{report_path.name}`" if report_path else "*(report could not be saved)*"
    )
    lines += [
        "",
        f"*Run at {config.timestamp[:19]}. Report: {saved_note}.*",
    ]
    return "\n".join(lines)


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
