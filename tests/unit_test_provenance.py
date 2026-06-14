"""
Stage 2 — Provenance backbone unit tests.

Covers:
  GenerationDecision.to_markdown()   — provenance fields render correctly
  VisionDecision.to_markdown()       — provenance fields + screenshot rendered
  emit_decision()                    — writes correct prefix; content is valid JSON
  list_artifacts()                   — returns healing + generation + vision files

All tests are isolated: they use temporary directories and do not touch
tests/artifacts/ on disk.
"""

import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from schemas.generation import GenerationDecision, VisionDecision

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_generation_decision(**kwargs) -> GenerationDecision:
    defaults = dict(
        url="https://example.com",
        story="Log in and verify welcome message",
        code="import { test } from '@playwright/test';\ntest('login', async ({ page }) => {});",
        line_count=2,
        model_used="qwen3-30b",
        provider="lm_studio",
        prompt_version="3",
        prompt_hash="abcdef123456",
        input_tokens=500,
        output_tokens=120,
        latency_ms=1234,
        retry_count=1,
        trace_id="trace-abc-001",
        context_snapshot_id="deadbeef1234",
    )
    defaults.update(kwargs)
    return GenerationDecision(**defaults)


def _make_vision_decision(**kwargs) -> VisionDecision:
    defaults = dict(
        url="https://saucedemo.com",
        instruction="Login with standard_user / secret_sauce",
        code="import { test } from '@playwright/test';\ntest('vision', async ({ page }) => {});",
        line_count=2,
        screenshot_path="/tmp/screenshot.png",
        model_used="llava-v1.5",
        provider="ollama",
        prompt_version="1",
        prompt_hash="feedface9999",
        input_tokens=300,
        output_tokens=80,
        latency_ms=2500,
        retry_count=0,
        trace_id="trace-vision-002",
    )
    defaults.update(kwargs)
    return VisionDecision(**defaults)


# ---------------------------------------------------------------------------
# GenerationDecision.to_markdown()
# ---------------------------------------------------------------------------


class TestGenerationDecisionToMarkdown(unittest.TestCase):
    """GenerationDecision.to_markdown() renders all provenance fields correctly."""

    def setUp(self):
        self.decision = _make_generation_decision()
        self.md = self.decision.to_markdown()

    def test_header_contains_generation_report(self):
        self.assertIn("# Generation Report", self.md)

    def test_url_rendered(self):
        self.assertIn("https://example.com", self.md)

    def test_story_rendered(self):
        self.assertIn("Log in and verify welcome message", self.md)

    def test_code_rendered(self):
        self.assertIn("@playwright/test", self.md)

    def test_line_count_rendered(self):
        self.assertIn("2 lines", self.md)

    def test_provenance_section_present(self):
        self.assertIn("## Provenance", self.md)

    def test_model_and_provider_rendered(self):
        self.assertIn("qwen3-30b", self.md)
        self.assertIn("lm_studio", self.md)

    def test_prompt_version_and_hash_rendered(self):
        self.assertIn("`3`", self.md)
        self.assertIn("`abcdef123456`", self.md)

    def test_latency_rendered(self):
        self.assertIn("1234 ms", self.md)

    def test_tokens_rendered(self):
        self.assertIn("500", self.md)  # input_tokens
        self.assertIn("120", self.md)  # output_tokens

    def test_trace_id_rendered(self):
        self.assertIn("`trace-abc-001`", self.md)

    def test_context_snapshot_id_rendered(self):
        self.assertIn("`deadbeef1234`", self.md)

    def test_unknown_model_shows_placeholder(self):
        d = _make_generation_decision(model_used="", provider="")
        md = d.to_markdown()
        self.assertIn("*(unknown)*", md)

    def test_no_latency_shows_placeholder(self):
        d = _make_generation_decision(latency_ms=0)
        md = d.to_markdown()
        self.assertIn("*(not recorded)*", md)

    def test_no_trace_shows_na(self):
        d = _make_generation_decision(trace_id="")
        md = d.to_markdown()
        self.assertIn("*(n/a)*", md)

    def test_round_trip_preserves_fields(self):
        json_str = self.decision.to_json()
        restored = GenerationDecision.model_validate_json(json_str)
        self.assertEqual(restored.url, "https://example.com")
        self.assertEqual(restored.model_used, "qwen3-30b")
        self.assertEqual(restored.latency_ms, 1234)
        self.assertEqual(restored.trace_id, "trace-abc-001")


# ---------------------------------------------------------------------------
# VisionDecision.to_markdown()
# ---------------------------------------------------------------------------


class TestVisionDecisionToMarkdown(unittest.TestCase):
    """VisionDecision.to_markdown() renders screenshot and provenance correctly."""

    def setUp(self):
        self.decision = _make_vision_decision()
        self.md = self.decision.to_markdown()

    def test_header_contains_vision_report(self):
        self.assertIn("# Vision Report", self.md)

    def test_url_rendered(self):
        self.assertIn("https://saucedemo.com", self.md)

    def test_instruction_rendered(self):
        self.assertIn("Login with standard_user", self.md)

    def test_screenshot_rendered(self):
        self.assertIn("/tmp/screenshot.png", self.md)

    def test_code_rendered(self):
        self.assertIn("@playwright/test", self.md)

    def test_provenance_section_present(self):
        self.assertIn("## Provenance", self.md)

    def test_model_and_provider_rendered(self):
        self.assertIn("llava-v1.5", self.md)
        self.assertIn("ollama", self.md)

    def test_latency_rendered(self):
        self.assertIn("2500 ms", self.md)

    def test_trace_id_rendered(self):
        self.assertIn("`trace-vision-002`", self.md)

    def test_no_screenshot_shows_placeholder(self):
        d = _make_vision_decision(screenshot_path=None)
        md = d.to_markdown()
        self.assertIn("*(not captured)*", md)

    def test_no_latency_shows_placeholder(self):
        d = _make_vision_decision(latency_ms=0)
        md = d.to_markdown()
        self.assertIn("*(not recorded)*", md)

    def test_round_trip_preserves_fields(self):
        json_str = self.decision.to_json()
        restored = VisionDecision.model_validate_json(json_str)
        self.assertEqual(restored.url, "https://saucedemo.com")
        self.assertEqual(restored.model_used, "llava-v1.5")
        self.assertEqual(restored.latency_ms, 2500)
        self.assertEqual(restored.trace_id, "trace-vision-002")
        self.assertEqual(restored.screenshot_path, "/tmp/screenshot.png")


# ---------------------------------------------------------------------------
# emit_decision()
# ---------------------------------------------------------------------------


class TestEmitDecision(unittest.TestCase):
    """emit_decision() writes a timestamped JSON file with the correct prefix."""

    def _emit(self, decision, prefix: str, tmp_dir: Path) -> Path:
        """Call emit_decision() redirected to a temp directory."""
        from src.healing.artifact_store import emit_decision

        with patch("src.healing.artifact_store.ARTIFACTS_DIR", tmp_dir):
            return emit_decision(decision, prefix)

    def test_generation_decision_file_has_correct_prefix(self):
        decision = _make_generation_decision()
        with tempfile.TemporaryDirectory() as tmpdir:
            path = self._emit(decision, "generation_decision", Path(tmpdir))
            self.assertTrue(path.name.startswith("generation_decision_"))
            self.assertTrue(path.name.endswith(".json"))

    def test_vision_decision_file_has_correct_prefix(self):
        decision = _make_vision_decision()
        with tempfile.TemporaryDirectory() as tmpdir:
            path = self._emit(decision, "vision_decision", Path(tmpdir))
            self.assertTrue(path.name.startswith("vision_decision_"))
            self.assertTrue(path.name.endswith(".json"))

    def test_written_file_is_valid_json(self):
        decision = _make_generation_decision()
        with tempfile.TemporaryDirectory() as tmpdir:
            path = self._emit(decision, "generation_decision", Path(tmpdir))
            raw = json.loads(path.read_text(encoding="utf-8"))
            self.assertIn("url", raw)
            self.assertIn("model_used", raw)
            self.assertIn("latency_ms", raw)

    def test_written_json_has_correct_field_values(self):
        decision = _make_generation_decision(
            url="https://test.example.com",
            model_used="test-model",
            latency_ms=999,
        )
        with tempfile.TemporaryDirectory() as tmpdir:
            path = self._emit(decision, "generation_decision", Path(tmpdir))
            raw = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(raw["url"], "https://test.example.com")
            self.assertEqual(raw["model_used"], "test-model")
            self.assertEqual(raw["latency_ms"], 999)

    def test_returns_path_object(self):
        decision = _make_generation_decision()
        with tempfile.TemporaryDirectory() as tmpdir:
            path = self._emit(decision, "generation_decision", Path(tmpdir))
            self.assertIsInstance(path, Path)
            self.assertTrue(path.exists())


# ---------------------------------------------------------------------------
# list_artifacts()
# ---------------------------------------------------------------------------


class TestListArtifacts(unittest.TestCase):
    """list_artifacts() surfaces healing, generation, and vision artifacts."""

    def _list(self, tmp_dir: Path) -> list[str]:
        from src.services.workbench_service import list_artifacts

        with patch("src.services.workbench_service._ARTIFACTS_DIR", tmp_dir):
            return list_artifacts()

    def _touch(self, tmp_dir: Path, name: str) -> Path:
        p = tmp_dir / name
        p.write_text("{}", encoding="utf-8")
        return p

    def test_returns_healing_decision_files(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            td = Path(tmpdir)
            self._touch(td, "healing_decision_20240101_120000.json")
            paths = self._list(td)
            self.assertEqual(len(paths), 1)
            self.assertIn("healing_decision_", paths[0])

    def test_returns_generation_decision_files(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            td = Path(tmpdir)
            self._touch(td, "generation_decision_20240101_120000.json")
            paths = self._list(td)
            self.assertEqual(len(paths), 1)
            self.assertIn("generation_decision_", paths[0])

    def test_returns_vision_decision_files(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            td = Path(tmpdir)
            self._touch(td, "vision_decision_20240101_120000.json")
            paths = self._list(td)
            self.assertEqual(len(paths), 1)
            self.assertIn("vision_decision_", paths[0])

    def test_returns_all_three_types_together(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            td = Path(tmpdir)
            self._touch(td, "healing_decision_20240101_120000.json")
            self._touch(td, "generation_decision_20240101_120001.json")
            self._touch(td, "vision_decision_20240101_120002.json")
            paths = self._list(td)
            self.assertEqual(len(paths), 3)
            names = [Path(p).name for p in paths]
            self.assertTrue(any("healing_decision_" in n for n in names))
            self.assertTrue(any("generation_decision_" in n for n in names))
            self.assertTrue(any("vision_decision_" in n for n in names))

    def test_excludes_execution_timeline_files(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            td = Path(tmpdir)
            self._touch(td, "execution_timeline_20240101_120000.json")
            self._touch(td, "healing_decision_20240101_120001.json")
            paths = self._list(td)
            self.assertEqual(len(paths), 1)
            self.assertNotIn("execution_timeline_", paths[0])

    def test_returns_empty_list_when_directory_absent(self):
        absent = Path("/tmp/_nonexistent_artifacts_dir_stage2_test")
        with patch("src.services.workbench_service._ARTIFACTS_DIR", absent):
            from src.services.workbench_service import list_artifacts

            paths = list_artifacts()
        self.assertEqual(paths, [])

    def test_returns_empty_list_when_no_matching_files(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            td = Path(tmpdir)
            self._touch(td, "execution_timeline_20240101_120000.json")
            self._touch(td, "some_other_file.json")
            paths = self._list(td)
            self.assertEqual(paths, [])


if __name__ == "__main__":
    unittest.main()
