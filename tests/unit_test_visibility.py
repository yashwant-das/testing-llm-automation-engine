"""
Stage 3 — Visibility unit tests.

Covers:
  HealingDecision.to_markdown()   — Evidence Context section rendered
  GenerationDecision.to_markdown() — Context Snapshot section expanded
  emit_artifacts()                 — one file written, no execution_timeline
  get_model_info()                 — model registry markdown table
"""

import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from schemas.artifacts import ContextSnapshot
from schemas.generation import GenerationDecision
from schemas.healing import (
    Evidence,
    HealingAction,
    HealingAnalysis,
    HealingDecision,
)
from schemas.shared import FailureType

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _minimal_action() -> HealingAction:
    return HealingAction(original_code="old", fixed_code="new", description="fix")


def _evidence_with_context() -> Evidence:
    return Evidence(
        error_log="Error: locator #btn not found",
        dom_snippet="<div><button id='btn'>Click</button></div>",
        accessibility_tree="button[name=Click]",
        locator_candidates=["#btn", "button >> text=Click", "[data-testid=submit]"],
        console_errors=["TypeError: cannot read property 'x' of undefined"],
    )


def _evidence_no_context() -> Evidence:
    return Evidence(error_log="Timeout 30000ms exceeded")


def _make_healing_decision(evidence: Evidence) -> HealingDecision:
    analysis = HealingAnalysis(
        failure_type=FailureType.LOCATOR_DRIFT,
        failure_summary="Locator drifted",
        hypothesis="Update selector",
        confidence_score=0.9,
        reasoning_steps=["step 1"],
        action_taken=_minimal_action(),
    )
    return HealingDecision.from_analysis(
        test_file="tests/e2e/click.spec.ts",
        analysis=analysis,
        evidence=evidence,
    )


def _make_generation_decision(snapshot: ContextSnapshot | None) -> GenerationDecision:
    return GenerationDecision(
        url="https://example.com",
        story="Login and verify",
        code="test('login', async ({page}) => {});",
        line_count=1,
        context_snapshot=snapshot,
    )


# ---------------------------------------------------------------------------
# HealingDecision — Evidence Context section (H3)
# ---------------------------------------------------------------------------


class TestHealingDecisionEvidenceContext(unittest.TestCase):
    """to_markdown() renders the Evidence Context section from Evidence fields."""

    def test_section_header_present(self):
        md = _make_healing_decision(_evidence_with_context()).to_markdown()
        self.assertIn("## Evidence Context", md)

    def test_dom_snippet_rendered(self):
        md = _make_healing_decision(_evidence_with_context()).to_markdown()
        self.assertIn("<button id='btn'>", md)

    def test_accessibility_tree_rendered(self):
        md = _make_healing_decision(_evidence_with_context()).to_markdown()
        self.assertIn("button[name=Click]", md)

    def test_locator_candidates_rendered(self):
        md = _make_healing_decision(_evidence_with_context()).to_markdown()
        self.assertIn("#btn", md)
        self.assertIn("button >> text=Click", md)
        self.assertIn("[data-testid=submit]", md)

    def test_console_errors_rendered(self):
        md = _make_healing_decision(_evidence_with_context()).to_markdown()
        self.assertIn("TypeError: cannot read property", md)

    def test_no_page_context_shows_placeholder(self):
        md = _make_healing_decision(_evidence_no_context()).to_markdown()
        self.assertIn("*(no page context collected)*", md)

    def test_dom_excerpt_capped_at_500_chars(self):
        long_dom = "<div>" + "x" * 1000 + "</div>"
        ev = Evidence(error_log="err", dom_snippet=long_dom)
        md = _make_healing_decision(ev).to_markdown()
        # The excerpt in the report should not contain more than 500 chars of dom
        # (plus the surrounding fenced block markers)
        dom_block_start = md.find("```html\n") + len("```html\n")
        dom_block_end = md.find("\n```", dom_block_start)
        dom_in_md = md[dom_block_start:dom_block_end]
        self.assertLessEqual(len(dom_in_md), 600)  # some slack for replaced backticks

    def test_locator_candidates_capped_at_10(self):
        ev = Evidence(
            error_log="err",
            locator_candidates=[f"#cand{i}" for i in range(20)],
        )
        md = _make_healing_decision(ev).to_markdown()
        # Only first 10 should appear
        self.assertIn("#cand9", md)
        self.assertNotIn("#cand10", md)


# ---------------------------------------------------------------------------
# GenerationDecision — Context Snapshot section (H3)
# ---------------------------------------------------------------------------


class TestGenerationDecisionContextSnapshot(unittest.TestCase):
    """to_markdown() renders the Context Snapshot section from ContextSnapshot."""

    def _snap(self) -> ContextSnapshot:
        return ContextSnapshot(
            url="https://example.com",
            html="<html><body><button>Go</button></body></html>",
            accessibility_tree="button[name=Go]",
            locator_candidates=["button >> text=Go", "#go-btn"],
            console_errors=["ReferenceError: x is not defined"],
        )

    def test_section_header_present(self):
        md = _make_generation_decision(self._snap()).to_markdown()
        self.assertIn("## Context Snapshot", md)

    def test_dom_rendered(self):
        md = _make_generation_decision(self._snap()).to_markdown()
        self.assertIn("<button>Go</button>", md)

    def test_accessibility_tree_rendered(self):
        md = _make_generation_decision(self._snap()).to_markdown()
        self.assertIn("button[name=Go]", md)

    def test_locator_candidates_rendered(self):
        md = _make_generation_decision(self._snap()).to_markdown()
        self.assertIn("button >> text=Go", md)
        self.assertIn("#go-btn", md)

    def test_console_errors_rendered(self):
        md = _make_generation_decision(self._snap()).to_markdown()
        self.assertIn("ReferenceError: x is not defined", md)

    def test_no_snapshot_shows_placeholder(self):
        md = _make_generation_decision(None).to_markdown()
        self.assertIn("*(no page context captured)*", md)

    def test_snapshot_id_rendered(self):
        d = GenerationDecision(
            url="https://example.com",
            story="test",
            code="test('t', () => {});",
            line_count=1,
            context_snapshot_id="abc123def456",
        )
        md = d.to_markdown()
        self.assertIn("abc123def456", md)


# ---------------------------------------------------------------------------
# emit_artifacts() — one file, no execution_timeline (M2)
# ---------------------------------------------------------------------------


class TestEmitArtifactsSingleFile(unittest.TestCase):
    """emit_artifacts() writes exactly one healing_decision_*.json file."""

    def _emit(self, tmpdir: Path):
        from schemas.healing import ExecutionTimeline
        from src.healing.artifact_store import emit_artifacts

        decision = _make_healing_decision(_evidence_no_context())
        timeline = ExecutionTimeline()
        timeline.add_step("Start", "Session started")
        with patch("src.healing.artifact_store.ARTIFACTS_DIR", tmpdir):
            emit_artifacts(decision, timeline)

    def test_exactly_one_file_written(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            self._emit(Path(tmpdir))
            files = list(Path(tmpdir).glob("*.json"))
            self.assertEqual(len(files), 1)

    def test_file_is_healing_decision(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            self._emit(Path(tmpdir))
            files = list(Path(tmpdir).glob("healing_decision_*.json"))
            self.assertEqual(len(files), 1)

    def test_no_execution_timeline_written(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            self._emit(Path(tmpdir))
            files = list(Path(tmpdir).glob("execution_timeline_*.json"))
            self.assertEqual(len(files), 0)


# ---------------------------------------------------------------------------
# get_model_info() — model registry panel (M4)
# ---------------------------------------------------------------------------


class TestGetModelInfo(unittest.TestCase):
    """get_model_info() returns a markdown table of registered models."""

    def _get(self, env: dict) -> str:
        from src.services.workbench_service import get_model_info

        with patch.dict("os.environ", env, clear=False):
            return get_model_info()

    def test_returns_markdown_table(self):
        md = self._get({"LM_STUDIO_TEXT_MODEL": "some-model"})
        self.assertIn("| Model ID |", md)
        self.assertIn("| --- |", md)

    def test_contains_model_registry_header(self):
        md = self._get({})
        self.assertIn("## Model Registry", md)

    def test_lists_lm_studio_model(self):
        md = self._get({"LM_STUDIO_TEXT_MODEL": "my-text-model"})
        self.assertIn("my-text-model", md)

    def test_lists_lm_studio_vision_model(self):
        md = self._get({"LM_STUDIO_VISION_MODEL": "my-vision-model"})
        self.assertIn("my-vision-model", md)

    def test_lists_ollama_model(self):
        md = self._get({"OLLAMA_TEXT_MODEL": "gemma4:26b"})
        self.assertIn("gemma4:26b", md)

    def test_vision_capable_shows_checkmark(self):
        md = self._get({"LM_STUDIO_VISION_MODEL": "my-vision-model"})
        self.assertIn("✅", md)

    def test_non_vision_model_shows_dash(self):
        # A text-only model must be distinct from the vision model so it gets
        # its own row with is_vision_capable=False.
        md = self._get(
            {
                "LM_STUDIO_TEXT_MODEL": "text-only-model",
                "LM_STUDIO_VISION_MODEL": "vision-model",
            }
        )
        self.assertIn(" — ", md)

    def test_provider_column_present(self):
        md = self._get({"LM_STUDIO_TEXT_MODEL": "some-model"})
        self.assertIn("lm_studio", md)

    def test_model_count_footer(self):
        md = self._get({"LM_STUDIO_TEXT_MODEL": "some-model"})
        self.assertIn("model(s) registered", md)

    def test_refresh_re_reads_env(self):
        """Calling get_model_info() twice with different env reflects changes."""
        md1 = self._get({"LM_STUDIO_TEXT_MODEL": "model-alpha"})
        md2 = self._get({"LM_STUDIO_TEXT_MODEL": "model-beta"})
        self.assertIn("model-alpha", md1)
        self.assertIn("model-beta", md2)
        self.assertNotIn("model-alpha", md2)


if __name__ == "__main__":
    unittest.main()
