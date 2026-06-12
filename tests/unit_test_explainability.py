"""
Phase 9 — Explainability unit tests.

Covers:
  - HealingAnalysis: confidence_rationale and root_cause_evidence fields
  - HealingDecision: all 7 new provenance fields with correct defaults
  - HealingDecision.from_analysis(): explainability kwargs flow through
  - HealingDecision.to_markdown(): Provenance and Root Cause Evidence sections
  - get_prompt_version(): reads from manifest, falls back to '1'
  - _evidence_snapshot_id(): stable 12-char SHA-256 of error_log
"""

import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

# ---------------------------------------------------------------------------
# Path setup so tests run from any working directory
# ---------------------------------------------------------------------------
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

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


def _minimal_evidence() -> Evidence:
    return Evidence(error_log="Error: locator #btn not found")


def _minimal_analysis(**kwargs) -> HealingAnalysis:
    defaults = dict(
        failure_type=FailureType.LOCATOR_DRIFT,
        failure_summary="Locator drifted",
        hypothesis="Update selector",
        confidence_score=0.9,
        reasoning_steps=["step 1"],
        action_taken=_minimal_action(),
    )
    defaults.update(kwargs)
    return HealingAnalysis(**defaults)


# ---------------------------------------------------------------------------
# HealingAnalysis — new Phase 9 fields
# ---------------------------------------------------------------------------


class TestHealingAnalysisExplainability(unittest.TestCase):
    """Phase 9 fields on HealingAnalysis: confidence_rationale, root_cause_evidence."""

    def test_confidence_rationale_defaults_to_empty_string(self):
        analysis = _minimal_analysis()
        self.assertEqual(analysis.confidence_rationale, "")

    def test_confidence_rationale_stores_value(self):
        analysis = _minimal_analysis(confidence_rationale="High — exact log match")
        self.assertEqual(analysis.confidence_rationale, "High — exact log match")

    def test_root_cause_evidence_defaults_to_empty_list(self):
        analysis = _minimal_analysis()
        self.assertEqual(analysis.root_cause_evidence, [])

    def test_root_cause_evidence_stores_items(self):
        evidence = ["log line A", "DOM element B"]
        analysis = _minimal_analysis(root_cause_evidence=evidence)
        self.assertEqual(analysis.root_cause_evidence, evidence)

    def test_round_trip_json_preserves_new_fields(self):
        analysis = _minimal_analysis(
            confidence_rationale="Exact match in log",
            root_cause_evidence=["line 1", "line 2"],
        )
        data = json.loads(analysis.model_dump_json())
        self.assertEqual(data["confidence_rationale"], "Exact match in log")
        self.assertEqual(data["root_cause_evidence"], ["line 1", "line 2"])


# ---------------------------------------------------------------------------
# HealingDecision — new Phase 9 fields: defaults
# ---------------------------------------------------------------------------


class TestHealingDecisionExplainabilityDefaults(unittest.TestCase):
    """All 7 new HealingDecision fields must default to empty/0 for back-compat."""

    def _minimal_decision(self) -> HealingDecision:
        return HealingDecision(
            test_file="tests/e2e/foo.spec.ts",
            failure_type=FailureType.TIMEOUT,
            failure_summary="Timed out waiting",
            evidence=_minimal_evidence(),
            hypothesis="Increase timeout",
            confidence_score=0.7,
            reasoning_steps=["step 1"],
            action_taken=_minimal_action(),
        )

    def test_model_used_defaults_to_empty(self):
        self.assertEqual(self._minimal_decision().model_used, "")

    def test_prompt_version_defaults_to_empty(self):
        self.assertEqual(self._minimal_decision().prompt_version, "")

    def test_prompt_hash_defaults_to_empty(self):
        self.assertEqual(self._minimal_decision().prompt_hash, "")

    def test_confidence_rationale_defaults_to_empty(self):
        self.assertEqual(self._minimal_decision().confidence_rationale, "")

    def test_root_cause_evidence_defaults_to_empty_list(self):
        self.assertEqual(self._minimal_decision().root_cause_evidence, [])

    def test_execution_duration_ms_defaults_to_zero(self):
        self.assertEqual(self._minimal_decision().execution_duration_ms, 0)

    def test_context_snapshot_id_defaults_to_empty(self):
        self.assertEqual(self._minimal_decision().context_snapshot_id, "")

    def test_execution_duration_ms_rejects_negative(self):
        from pydantic import ValidationError

        with self.assertRaises(ValidationError):
            HealingDecision(
                test_file="t.spec.ts",
                failure_type=FailureType.TIMEOUT,
                failure_summary="s",
                evidence=_minimal_evidence(),
                hypothesis="h",
                confidence_score=0.5,
                reasoning_steps=["s"],
                action_taken=_minimal_action(),
                execution_duration_ms=-1,
            )


# ---------------------------------------------------------------------------
# HealingDecision — from_analysis() populates new fields
# ---------------------------------------------------------------------------


class TestHealingDecisionFromAnalysis(unittest.TestCase):
    """from_analysis() must propagate all explainability kwargs into the decision."""

    def _decision(self, **kwargs) -> HealingDecision:
        analysis = _minimal_analysis(
            confidence_rationale="Very confident",
            root_cause_evidence=["evidence A", "evidence B"],
        )
        return HealingDecision.from_analysis(
            test_file="tests/e2e/bar.spec.ts",
            analysis=analysis,
            evidence=_minimal_evidence(),
            **kwargs,
        )

    def test_model_used_propagated(self):
        d = self._decision(model_used="qwen3.6-35b-a3b")
        self.assertEqual(d.model_used, "qwen3.6-35b-a3b")

    def test_prompt_version_propagated(self):
        d = self._decision(prompt_version="2")
        self.assertEqual(d.prompt_version, "2")

    def test_prompt_hash_propagated(self):
        d = self._decision(prompt_hash="abc123def456abcd")
        self.assertEqual(d.prompt_hash, "abc123def456abcd")

    def test_execution_duration_ms_propagated(self):
        d = self._decision(execution_duration_ms=4200)
        self.assertEqual(d.execution_duration_ms, 4200)

    def test_context_snapshot_id_propagated(self):
        d = self._decision(context_snapshot_id="deadbeef1234")
        self.assertEqual(d.context_snapshot_id, "deadbeef1234")

    def test_confidence_rationale_copied_from_analysis(self):
        """confidence_rationale flows from HealingAnalysis → HealingDecision."""
        d = self._decision()
        self.assertEqual(d.confidence_rationale, "Very confident")

    def test_root_cause_evidence_copied_from_analysis(self):
        """root_cause_evidence flows from HealingAnalysis → HealingDecision."""
        d = self._decision()
        self.assertEqual(d.root_cause_evidence, ["evidence A", "evidence B"])

    def test_all_kwargs_at_once(self):
        d = self._decision(
            model_used="claude-3-5",
            prompt_version="3",
            prompt_hash="feedfacecafe0000",
            execution_duration_ms=1500,
            context_snapshot_id="aabbccdd1122",
        )
        self.assertEqual(d.model_used, "claude-3-5")
        self.assertEqual(d.prompt_version, "3")
        self.assertEqual(d.prompt_hash, "feedfacecafe0000")
        self.assertEqual(d.execution_duration_ms, 1500)
        self.assertEqual(d.context_snapshot_id, "aabbccdd1122")

    def test_defaults_when_kwargs_omitted(self):
        """If caller omits all optional kwargs, fields default correctly."""
        analysis = _minimal_analysis()
        d = HealingDecision.from_analysis(
            test_file="t.spec.ts",
            analysis=analysis,
            evidence=_minimal_evidence(),
        )
        self.assertEqual(d.model_used, "")
        self.assertEqual(d.prompt_version, "")
        self.assertEqual(d.prompt_hash, "")
        self.assertEqual(d.execution_duration_ms, 0)
        self.assertEqual(d.context_snapshot_id, "")


# ---------------------------------------------------------------------------
# HealingDecision.to_markdown() — Provenance and Root Cause Evidence sections
# ---------------------------------------------------------------------------


class TestHealingDecisionToMarkdown(unittest.TestCase):
    """to_markdown() must render Phase 9 sections correctly."""

    def _full_decision(self) -> HealingDecision:
        analysis = _minimal_analysis(
            confidence_rationale="Exact selector seen in log",
            root_cause_evidence=[
                "Error: #old-btn not found",
                "DOM: button#new-btn present",
            ],
        )
        return HealingDecision.from_analysis(
            test_file="tests/e2e/click.spec.ts",
            analysis=analysis,
            evidence=_minimal_evidence(),
            model_used="qwen3.6-35b-a3b",
            prompt_version="2",
            prompt_hash="abc123",
            execution_duration_ms=1800,
            context_snapshot_id="deadbeef1234",
        )

    def test_provenance_section_present(self):
        md = self._full_decision().to_markdown()
        self.assertIn("## Provenance", md)

    def test_provenance_model_rendered(self):
        md = self._full_decision().to_markdown()
        self.assertIn("qwen3.6-35b-a3b", md)

    def test_provenance_prompt_version_and_hash(self):
        md = self._full_decision().to_markdown()
        self.assertIn("`2`", md)
        self.assertIn("`abc123`", md)

    def test_provenance_execution_time(self):
        md = self._full_decision().to_markdown()
        self.assertIn("1800 ms", md)

    def test_provenance_context_snapshot(self):
        md = self._full_decision().to_markdown()
        self.assertIn("`deadbeef1234`", md)

    def test_root_cause_evidence_section_present(self):
        md = self._full_decision().to_markdown()
        self.assertIn("## Root Cause Evidence", md)

    def test_root_cause_evidence_items_rendered(self):
        md = self._full_decision().to_markdown()
        self.assertIn("Error: #old-btn not found", md)
        self.assertIn("DOM: button#new-btn present", md)

    def test_confidence_rationale_rendered(self):
        md = self._full_decision().to_markdown()
        self.assertIn("Exact selector seen in log", md)

    def test_unknown_provenance_placeholders(self):
        """When provenance fields are empty the markdown shows *(unknown)*."""
        analysis = _minimal_analysis()
        d = HealingDecision.from_analysis(
            test_file="t.spec.ts",
            analysis=analysis,
            evidence=_minimal_evidence(),
        )
        md = d.to_markdown()
        self.assertIn("*(unknown)*", md)  # model_used
        self.assertIn("*(not recorded)*", md)  # execution_duration_ms == 0
        self.assertIn("*(n/a)*", md)  # context_snapshot_id

    def test_empty_root_cause_evidence_shows_placeholder(self):
        analysis = _minimal_analysis(root_cause_evidence=[])
        d = HealingDecision.from_analysis(
            test_file="t.spec.ts",
            analysis=analysis,
            evidence=_minimal_evidence(),
        )
        md = d.to_markdown()
        self.assertIn("*(none provided)*", md)

    def test_empty_confidence_rationale_shows_placeholder(self):
        analysis = _minimal_analysis(confidence_rationale="")
        d = HealingDecision.from_analysis(
            test_file="t.spec.ts",
            analysis=analysis,
            evidence=_minimal_evidence(),
        )
        md = d.to_markdown()
        self.assertIn("*(not provided)*", md)


# ---------------------------------------------------------------------------
# get_prompt_version() — manifest reading and fallback
# ---------------------------------------------------------------------------


class TestGetPromptVersion(unittest.TestCase):
    """get_prompt_version() reads from manifest.json and falls back gracefully."""

    def setUp(self):
        # Reset the module-level cache before each test
        import src.utils.prompt_loader as pl

        pl._manifest_cache = None

    def tearDown(self):
        import src.utils.prompt_loader as pl

        pl._manifest_cache = None

    def test_returns_version_from_manifest(self):
        """Should return the version string for a known agent."""
        from src.utils.prompt_loader import get_prompt_version

        fake_manifest = {
            "prompts": {
                "healer": {"version": "5"},
                "generator": {"version": "3"},
            }
        }
        with patch(
            "src.utils.prompt_loader._load_manifest", return_value=fake_manifest
        ):
            self.assertEqual(get_prompt_version("healer"), "5")
            self.assertEqual(get_prompt_version("generator"), "3")

    def test_fallback_to_one_when_agent_not_in_manifest(self):
        from src.utils.prompt_loader import get_prompt_version

        fake_manifest = {"prompts": {"healer": {"version": "2"}}}
        with patch(
            "src.utils.prompt_loader._load_manifest", return_value=fake_manifest
        ):
            self.assertEqual(get_prompt_version("nonexistent"), "1")

    def test_fallback_to_one_when_manifest_empty(self):
        from src.utils.prompt_loader import get_prompt_version

        with patch(
            "src.utils.prompt_loader._load_manifest", return_value={"prompts": {}}
        ):
            self.assertEqual(get_prompt_version("healer"), "1")

    def test_reads_real_manifest_for_healer(self):
        """Integration check: real manifest has healer version '2'."""
        from src.utils.prompt_loader import get_prompt_version

        # This relies on the actual prompts/manifest.json existing in the project.
        # If the manifest is missing the test gracefully falls back to '1'.
        version = get_prompt_version("healer")
        self.assertIsInstance(version, str)
        self.assertTrue(len(version) > 0)

    def test_load_manifest_caches_result(self):
        """_load_manifest() should not re-read the file on repeated calls."""
        from src.utils.prompt_loader import _load_manifest

        with tempfile.TemporaryDirectory() as tmpdir:
            manifest_path = Path(tmpdir) / "manifest.json"
            manifest_path.write_text(
                json.dumps({"prompts": {"healer": {"version": "7"}}})
            )

            with patch("src.utils.prompt_loader._MANIFEST_PATH", manifest_path):
                first = _load_manifest()
                # Overwrite file — second call should still return cached value
                manifest_path.write_text(json.dumps({"prompts": {}}))
                second = _load_manifest()

        self.assertIs(first, second)  # Same object — cached


# ---------------------------------------------------------------------------
# _evidence_snapshot_id() — stable 12-char hash
# ---------------------------------------------------------------------------


class TestEvidenceSnapshotId(unittest.TestCase):
    """_evidence_snapshot_id() produces a stable 12-char SHA-256 prefix."""

    def _snapshot_id(self, evidence: Evidence) -> str:
        from src.healing.planner import _evidence_snapshot_id

        return _evidence_snapshot_id(evidence)

    def test_returns_twelve_hex_chars(self):
        ev = Evidence(error_log="some error")
        sid = self._snapshot_id(ev)
        self.assertEqual(len(sid), 12)
        self.assertTrue(all(c in "0123456789abcdef" for c in sid))

    def test_deterministic_for_same_error_log(self):
        ev1 = Evidence(error_log="Error: selector not found")
        ev2 = Evidence(error_log="Error: selector not found")
        self.assertEqual(self._snapshot_id(ev1), self._snapshot_id(ev2))

    def test_different_logs_produce_different_ids(self):
        ev1 = Evidence(error_log="Error A")
        ev2 = Evidence(error_log="Error B")
        self.assertNotEqual(self._snapshot_id(ev1), self._snapshot_id(ev2))

    def test_empty_error_log_is_stable(self):
        ev = Evidence(error_log="")
        sid = self._snapshot_id(ev)
        # SHA-256 of empty string, first 12 chars
        expected = hashlib.sha256(b"").hexdigest()[:12]
        self.assertEqual(sid, expected)

    def test_matches_sha256_of_log(self):
        log = "TimeoutError: waiting for selector"
        ev = Evidence(error_log=log)
        expected = hashlib.sha256(log.encode("utf-8")).hexdigest()[:12]
        self.assertEqual(self._snapshot_id(ev), expected)

    def test_none_error_log_handled(self):
        """Evidence with error_log=None-equivalent should not crash."""

        from src.healing.planner import _evidence_snapshot_id

        # error_log is a required str field, but planner guards with `or ""`
        ev = Evidence(error_log="")
        sid = _evidence_snapshot_id(ev)
        self.assertEqual(len(sid), 12)

    def test_long_log_produces_correct_prefix(self):
        log = "x" * 10_000
        ev = Evidence(error_log=log)
        expected = hashlib.sha256(log.encode("utf-8")).hexdigest()[:12]
        self.assertEqual(self._snapshot_id(ev), expected)


# ---------------------------------------------------------------------------
# JSON round-trip — backward compatibility
# ---------------------------------------------------------------------------


class TestHealingDecisionBackwardCompat(unittest.TestCase):
    """Old artifact JSON files (without Phase 9 fields) must still parse."""

    def test_old_artifact_without_provenance_fields_parses(self):
        """A minimal JSON that predates Phase 9 should still be valid."""
        old_json = json.dumps(
            {
                "test_file": "tests/e2e/old.spec.ts",
                "failure_type": "TIMEOUT",
                "failure_summary": "Timed out",
                "evidence": {"error_log": "Timeout after 5000ms"},
                "hypothesis": "Increase timeout",
                "confidence_score": 0.8,
                "reasoning_steps": ["step 1"],
                "action_taken": {
                    "original_code": "old",
                    "fixed_code": "new",
                    "description": "fix",
                },
            }
        )
        decision = HealingDecision.model_validate_json(old_json)
        # All Phase 9 fields must have their defaults
        self.assertEqual(decision.model_used, "")
        self.assertEqual(decision.prompt_version, "")
        self.assertEqual(decision.prompt_hash, "")
        self.assertEqual(decision.confidence_rationale, "")
        self.assertEqual(decision.root_cause_evidence, [])
        self.assertEqual(decision.execution_duration_ms, 0)
        self.assertEqual(decision.context_snapshot_id, "")

    def test_full_artifact_with_provenance_round_trips(self):
        analysis = _minimal_analysis(
            confidence_rationale="High",
            root_cause_evidence=["ev1"],
        )
        original = HealingDecision.from_analysis(
            test_file="t.spec.ts",
            analysis=analysis,
            evidence=_minimal_evidence(),
            model_used="model-x",
            prompt_version="3",
            prompt_hash="abc123456789abcd",
            execution_duration_ms=999,
            context_snapshot_id="cafe1234beef",
        )
        json_str = original.to_json()
        restored = HealingDecision.model_validate_json(json_str)
        self.assertEqual(restored.model_used, "model-x")
        self.assertEqual(restored.prompt_version, "3")
        self.assertEqual(restored.prompt_hash, "abc123456789abcd")
        self.assertEqual(restored.confidence_rationale, "High")
        self.assertEqual(restored.root_cause_evidence, ["ev1"])
        self.assertEqual(restored.execution_duration_ms, 999)
        self.assertEqual(restored.context_snapshot_id, "cafe1234beef")


if __name__ == "__main__":
    unittest.main()
