"""
Unit tests for Phase 8 — Observability.

Coverage:
    TestTraceMetadataSchema   — TraceMetadata Pydantic model
    TestSubprocessSpanSchema  — SubprocessSpan Pydantic model
    TestSessionSpanSchema     — SessionSpan Pydantic model
    TestTraceSession          — TraceSession aggregation (to_session_span)
    TestTraceWriter           — JSONL file writing, thread safety, read_all
    TestTracer                — Tracer lifecycle: start/record/end
    TestNullTracer            — NullTracer no-ops
    TestGlobalTracer          — get_tracer / configure_tracer
    TestRouterInstrumentation — LLMRouter records spans when tracer is active
"""

from __future__ import annotations

import json
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from schemas.artifacts import TraceMetadata
from src.observability import Tracer, configure_tracer, get_tracer
from src.observability.schemas import (
    SessionSpan,
    SubprocessSpan,
    TraceSession,
)
from src.observability.tracer import NullTracer as NullTracerDirect
from src.observability.tracer import Tracer as TracerDirect
from src.observability.writer import TraceWriter

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_writer(tmp_dir: str) -> TraceWriter:
    return TraceWriter(Path(tmp_dir) / "traces.jsonl")


def _make_tracer(tmp_dir: str) -> Tracer:
    return Tracer(_make_writer(tmp_dir))


def _make_llm_response(
    model_used: str = "test-model",
    provider: str = "test-provider",
    input_tokens: int = 100,
    output_tokens: int = 50,
    latency_ms: int = 200,
    retry_count: int = 0,
) -> MagicMock:
    resp = MagicMock()
    resp.model_used = model_used
    resp.provider = provider
    resp.input_tokens = input_tokens
    resp.output_tokens = output_tokens
    resp.latency_ms = latency_ms
    resp.retry_count = retry_count
    return resp


# ===========================================================================
# 1. TraceMetadata Schema
# ===========================================================================


class TestTraceMetadataSchema(unittest.TestCase):
    def test_defaults(self):
        m = TraceMetadata(
            trace_id="abc123",
            operation_id="op001",
            model="gpt-4",
        )
        self.assertEqual(m.span_type, "llm")
        self.assertEqual(m.model_version, "")
        self.assertEqual(m.prompt_version, "")
        self.assertEqual(m.prompt_hash, "")
        self.assertEqual(m.input_tokens, 0)
        self.assertEqual(m.output_tokens, 0)
        self.assertEqual(m.latency_ms, 0)
        self.assertEqual(m.retry_count, 0)
        self.assertIsNone(m.failure_reason)
        self.assertTrue(m.timestamp)

    def test_full_fields(self):
        m = TraceMetadata(
            trace_id="t1",
            operation_id="op1",
            model="qwen3",
            model_version="30b",
            prompt_version="healer",
            prompt_hash="abc123def456",
            input_tokens=512,
            output_tokens=256,
            latency_ms=1234,
            retry_count=1,
            failure_reason="rate limit",
        )
        self.assertEqual(m.model, "qwen3")
        self.assertEqual(m.input_tokens, 512)
        self.assertEqual(m.retry_count, 1)
        self.assertEqual(m.failure_reason, "rate limit")

    def test_json_round_trip(self):
        m = TraceMetadata(trace_id="t1", operation_id="op1", model="m1")
        payload = json.loads(m.model_dump_json())
        self.assertEqual(payload["span_type"], "llm")
        self.assertEqual(payload["trace_id"], "t1")
        self.assertIn("timestamp", payload)


# ===========================================================================
# 2. SubprocessSpan Schema
# ===========================================================================


class TestSubprocessSpanSchema(unittest.TestCase):
    def test_defaults(self):
        s = SubprocessSpan(
            trace_id="t1",
            operation_id="op1",
            command="npx playwright test foo.spec.ts",
            exit_code=0,
            latency_ms=500,
            success=True,
        )
        self.assertEqual(s.span_type, "subprocess")
        self.assertTrue(s.success)
        self.assertTrue(s.timestamp)

    def test_failure_exit_code(self):
        s = SubprocessSpan(
            trace_id="t1",
            operation_id="op1",
            command="npx playwright test bar.spec.ts",
            exit_code=1,
            latency_ms=300,
            success=False,
        )
        self.assertFalse(s.success)
        self.assertEqual(s.exit_code, 1)

    def test_json_round_trip(self):
        s = SubprocessSpan(
            trace_id="t1",
            operation_id="op1",
            command="cmd",
            exit_code=0,
            latency_ms=100,
            success=True,
        )
        payload = json.loads(s.model_dump_json())
        self.assertEqual(payload["span_type"], "subprocess")


# ===========================================================================
# 3. SessionSpan Schema
# ===========================================================================


class TestSessionSpanSchema(unittest.TestCase):
    def test_defaults(self):
        s = SessionSpan(
            trace_id="t1",
            session_type="healing",
            total_latency_ms=5000,
            llm_call_count=3,
            subprocess_call_count=4,
            total_input_tokens=1500,
            total_output_tokens=750,
            total_retry_count=1,
            success=True,
        )
        self.assertEqual(s.span_type, "session")
        self.assertTrue(s.success)
        self.assertEqual(s.llm_call_count, 3)

    def test_json_round_trip(self):
        s = SessionSpan(
            trace_id="t1",
            session_type="generation",
            total_latency_ms=1000,
            llm_call_count=1,
            subprocess_call_count=0,
            total_input_tokens=200,
            total_output_tokens=100,
            total_retry_count=0,
            success=True,
        )
        payload = json.loads(s.model_dump_json())
        self.assertEqual(payload["span_type"], "session")
        self.assertEqual(payload["session_type"], "generation")


# ===========================================================================
# 4. TraceSession (in-memory accumulator)
# ===========================================================================


class TestTraceSession(unittest.TestCase):
    def _make_session(self, session_type: str = "healing") -> TraceSession:
        return TraceSession(
            trace_id="sess-001",
            session_type=session_type,
            start_monotonic=time.monotonic() - 2.0,  # 2 seconds ago
        )

    def test_empty_to_session_span(self):
        session = self._make_session()
        span = session.to_session_span(current_monotonic=time.monotonic(), success=True)
        self.assertEqual(span.trace_id, "sess-001")
        self.assertEqual(span.session_type, "healing")
        self.assertEqual(span.llm_call_count, 0)
        self.assertEqual(span.subprocess_call_count, 0)
        self.assertEqual(span.total_input_tokens, 0)
        self.assertEqual(span.total_output_tokens, 0)
        self.assertEqual(span.total_retry_count, 0)
        self.assertTrue(span.success)
        self.assertGreater(span.total_latency_ms, 0)

    def test_aggregates_llm_spans(self):
        session = self._make_session()
        session.llm_spans = [
            TraceMetadata(
                trace_id="sess-001",
                operation_id="op1",
                model="m",
                input_tokens=100,
                output_tokens=50,
                latency_ms=200,
                retry_count=1,
            ),
            TraceMetadata(
                trace_id="sess-001",
                operation_id="op2",
                model="m",
                input_tokens=200,
                output_tokens=80,
                latency_ms=300,
                retry_count=0,
            ),
        ]
        span = session.to_session_span(
            current_monotonic=time.monotonic(), success=False
        )
        self.assertEqual(span.llm_call_count, 2)
        self.assertEqual(span.total_input_tokens, 300)
        self.assertEqual(span.total_output_tokens, 130)
        self.assertEqual(span.total_retry_count, 1)
        self.assertFalse(span.success)

    def test_aggregates_subprocess_spans(self):
        session = self._make_session()
        session.subprocess_spans = [
            SubprocessSpan(
                trace_id="sess-001",
                operation_id="sp1",
                command="npx playwright test a.spec.ts",
                exit_code=0,
                latency_ms=1000,
                success=True,
            ),
            SubprocessSpan(
                trace_id="sess-001",
                operation_id="sp2",
                command="npx playwright test a.spec.ts",
                exit_code=1,
                latency_ms=2000,
                success=False,
            ),
        ]
        span = session.to_session_span(
            current_monotonic=time.monotonic(), success=False
        )
        self.assertEqual(span.subprocess_call_count, 2)


# ===========================================================================
# 5. TraceWriter
# ===========================================================================


class TestTraceWriter(unittest.TestCase):
    def test_write_creates_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            writer = _make_writer(tmp)
            span = TraceMetadata(trace_id="t1", operation_id="op1", model="m")
            writer.write_span(span)
            self.assertTrue(writer.output_path.exists())

    def test_write_appends_jsonl(self):
        with tempfile.TemporaryDirectory() as tmp:
            writer = _make_writer(tmp)
            for i in range(3):
                writer.write_span(
                    TraceMetadata(trace_id=f"t{i}", operation_id=f"op{i}", model="m")
                )
            lines = writer.output_path.read_text().strip().splitlines()
            self.assertEqual(len(lines), 3)
            for line in lines:
                obj = json.loads(line)
                self.assertEqual(obj["span_type"], "llm")

    def test_read_all_returns_dicts(self):
        with tempfile.TemporaryDirectory() as tmp:
            writer = _make_writer(tmp)
            writer.write_span(
                TraceMetadata(trace_id="t1", operation_id="op1", model="m1")
            )
            writer.write_span(
                SubprocessSpan(
                    trace_id="t1",
                    operation_id="op2",
                    command="cmd",
                    exit_code=0,
                    latency_ms=100,
                    success=True,
                )
            )
            spans = writer.read_all()
            self.assertEqual(len(spans), 2)
            types = {s["span_type"] for s in spans}
            self.assertIn("llm", types)
            self.assertIn("subprocess", types)

    def test_read_all_nonexistent_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            writer = TraceWriter(Path(tmp) / "nonexistent.jsonl")
            self.assertEqual(writer.read_all(), [])

    def test_write_is_thread_safe(self):
        """Multiple threads writing simultaneously must not corrupt the file."""
        with tempfile.TemporaryDirectory() as tmp:
            writer = _make_writer(tmp)
            errors = []

            def write_10():
                try:
                    for i in range(10):
                        writer.write_span(
                            TraceMetadata(
                                trace_id="t", operation_id=f"op-{i}", model="m"
                            )
                        )
                except Exception as exc:
                    errors.append(exc)

            threads = [threading.Thread(target=write_10) for _ in range(5)]
            for t in threads:
                t.start()
            for t in threads:
                t.join()

            self.assertEqual(errors, [])
            spans = writer.read_all()
            self.assertEqual(len(spans), 50)

    def test_write_creates_parent_dirs(self):
        with tempfile.TemporaryDirectory() as tmp:
            writer = TraceWriter(Path(tmp) / "nested" / "deep" / "traces.jsonl")
            writer.write_span(
                TraceMetadata(trace_id="t1", operation_id="op1", model="m")
            )
            self.assertTrue(writer.output_path.exists())


# ===========================================================================
# 6. Tracer lifecycle
# ===========================================================================


class TestTracer(unittest.TestCase):
    def setUp(self):
        # Clear any thread-local session state left by previous tests so each
        # test starts with a clean slate (no leaked session on this thread).
        from src.observability.tracer import _thread_local

        _thread_local.session = None

    def tearDown(self):
        from src.observability.tracer import _thread_local

        _thread_local.session = None

    def test_start_session_returns_trace_id(self):
        with tempfile.TemporaryDirectory() as tmp:
            tracer = _make_tracer(tmp)
            trace_id = tracer.start_session("healing")
            self.assertIsInstance(trace_id, str)
            self.assertTrue(trace_id)  # non-empty

    def test_get_session_returns_active_session(self):
        with tempfile.TemporaryDirectory() as tmp:
            tracer = _make_tracer(tmp)
            trace_id = tracer.start_session("healing")
            session = tracer.get_session(trace_id)
            self.assertIsNotNone(session)
            self.assertEqual(session.trace_id, trace_id)
            self.assertEqual(session.session_type, "healing")

    def test_get_session_wrong_id_returns_none(self):
        with tempfile.TemporaryDirectory() as tmp:
            tracer = _make_tracer(tmp)
            tracer.start_session("healing")
            self.assertIsNone(tracer.get_session("wrong-id"))

    def test_get_session_before_start_returns_none(self):
        with tempfile.TemporaryDirectory() as tmp:
            tracer = _make_tracer(tmp)
            self.assertIsNone(tracer.get_session("any-id"))

    def test_record_llm_response_on_active_session(self):
        with tempfile.TemporaryDirectory() as tmp:
            tracer = _make_tracer(tmp)
            trace_id = tracer.start_session("healing")
            response = _make_llm_response(
                input_tokens=100, output_tokens=50, latency_ms=200
            )
            span = tracer.record_llm_response(response)
            self.assertIsNotNone(span)
            self.assertEqual(span.trace_id, trace_id)
            self.assertEqual(span.input_tokens, 100)
            self.assertEqual(span.output_tokens, 50)
            self.assertEqual(span.latency_ms, 200)

    def test_record_llm_response_no_session_returns_none(self):
        with tempfile.TemporaryDirectory() as tmp:
            tracer = _make_tracer(tmp)
            response = _make_llm_response()
            result = tracer.record_llm_response(response)
            self.assertIsNone(result)

    def test_record_llm_accumulates_in_session(self):
        with tempfile.TemporaryDirectory() as tmp:
            tracer = _make_tracer(tmp)
            trace_id = tracer.start_session("healing")
            tracer.record_llm_response(_make_llm_response(input_tokens=100))
            tracer.record_llm_response(_make_llm_response(input_tokens=200))
            session = tracer.get_session(trace_id)
            self.assertEqual(len(session.llm_spans), 2)

    def test_record_subprocess_on_active_session(self):
        with tempfile.TemporaryDirectory() as tmp:
            tracer = _make_tracer(tmp)
            trace_id = tracer.start_session("healing")
            span = tracer.record_subprocess(
                command="npx playwright test foo.spec.ts", exit_code=0, latency_ms=500
            )
            self.assertIsNotNone(span)
            self.assertEqual(span.trace_id, trace_id)
            self.assertTrue(span.success)
            self.assertEqual(span.exit_code, 0)
            self.assertEqual(span.latency_ms, 500)

    def test_record_subprocess_no_session_returns_none(self):
        with tempfile.TemporaryDirectory() as tmp:
            tracer = _make_tracer(tmp)
            result = tracer.record_subprocess(
                command="cmd", exit_code=0, latency_ms=100
            )
            self.assertIsNone(result)

    def test_set_prompt_context_reflected_in_span(self):
        with tempfile.TemporaryDirectory() as tmp:
            tracer = _make_tracer(tmp)
            tracer.start_session("healing")
            tracer.set_prompt_context("healer", "abc123")
            span = tracer.record_llm_response(_make_llm_response())
            self.assertEqual(span.prompt_version, "healer")
            self.assertEqual(span.prompt_hash, "abc123")

    def test_end_session_writes_session_span(self):
        with tempfile.TemporaryDirectory() as tmp:
            tracer = _make_tracer(tmp)
            trace_id = tracer.start_session("healing")
            tracer.record_llm_response(
                _make_llm_response(input_tokens=100, output_tokens=50)
            )
            tracer.record_subprocess(command="cmd", exit_code=0, latency_ms=500)
            session_span = tracer.end_session(trace_id, success=True)
            self.assertIsNotNone(session_span)
            self.assertEqual(session_span.trace_id, trace_id)
            self.assertTrue(session_span.success)
            self.assertEqual(session_span.llm_call_count, 1)
            self.assertEqual(session_span.subprocess_call_count, 1)
            self.assertEqual(session_span.total_input_tokens, 100)
            self.assertEqual(session_span.total_output_tokens, 50)

    def test_end_session_clears_session(self):
        with tempfile.TemporaryDirectory() as tmp:
            tracer = _make_tracer(tmp)
            trace_id = tracer.start_session("healing")
            tracer.end_session(trace_id, success=True)
            self.assertIsNone(tracer.get_session(trace_id))

    def test_end_session_wrong_id_is_noop(self):
        with tempfile.TemporaryDirectory() as tmp:
            tracer = _make_tracer(tmp)
            tracer.start_session("healing")
            result = tracer.end_session("wrong-id", success=True)
            self.assertIsNone(result)

    def test_end_session_writes_all_three_span_types(self):
        """After end_session, JSONL should contain llm, subprocess, and session spans."""
        with tempfile.TemporaryDirectory() as tmp:
            tracer = _make_tracer(tmp)
            writer = tracer._writer
            trace_id = tracer.start_session("healing")
            tracer.record_llm_response(_make_llm_response())
            tracer.record_subprocess(command="cmd", exit_code=0, latency_ms=100)
            tracer.end_session(trace_id, success=True)

            spans = writer.read_all()
            span_types = {s["span_type"] for s in spans}
            self.assertIn("llm", span_types)
            self.assertIn("subprocess", span_types)
            self.assertIn("session", span_types)

    def test_two_sessions_same_thread_replace(self):
        """Starting a second session on the same thread replaces the first."""
        with tempfile.TemporaryDirectory() as tmp:
            tracer = _make_tracer(tmp)
            id1 = tracer.start_session("healing")
            id2 = tracer.start_session("generation")
            self.assertNotEqual(id1, id2)
            # Old session no longer active
            self.assertIsNone(tracer.get_session(id1))
            self.assertIsNotNone(tracer.get_session(id2))

    def test_sessions_isolated_across_threads(self):
        """Each thread has its own independent session."""
        with tempfile.TemporaryDirectory() as tmp:
            tracer = _make_tracer(tmp)
            results = {}

            def run_session(session_type: str, n_tokens: int):
                tid = tracer.start_session(session_type)
                tracer.record_llm_response(_make_llm_response(input_tokens=n_tokens))
                session = tracer.get_session(tid)
                results[session_type] = len(session.llm_spans)
                tracer.end_session(tid, success=True)

            t1 = threading.Thread(target=run_session, args=("healing", 100))
            t2 = threading.Thread(target=run_session, args=("generation", 200))
            t1.start()
            t2.start()
            t1.join()
            t2.join()

            self.assertEqual(results.get("healing"), 1)
            self.assertEqual(results.get("generation"), 1)


# ===========================================================================
# 7. NullTracer
# ===========================================================================


class TestNullTracer(unittest.TestCase):
    def setUp(self):
        self.tracer = NullTracerDirect()

    def test_start_session_returns_empty_string(self):
        self.assertEqual(self.tracer.start_session("healing"), "")

    def test_set_prompt_context_no_error(self):
        self.tracer.set_prompt_context("healer", "abc")  # must not raise

    def test_record_llm_response_returns_none(self):
        response = _make_llm_response()
        self.assertIsNone(self.tracer.record_llm_response(response))

    def test_record_subprocess_returns_none(self):
        self.assertIsNone(
            self.tracer.record_subprocess(command="cmd", exit_code=0, latency_ms=100)
        )

    def test_end_session_returns_none(self):
        self.assertIsNone(self.tracer.end_session("any", success=True))

    def test_get_session_returns_none(self):
        self.assertIsNone(self.tracer.get_session("any"))


# ===========================================================================
# 8. Global tracer (get_tracer / configure_tracer)
# ===========================================================================


class TestGlobalTracer(unittest.TestCase):
    def test_default_is_null_tracer(self):
        import src.observability as obs

        original = obs._tracer
        # NullTracer is the default (set at module load)
        self.assertIsInstance(original, NullTracerDirect)

    def test_configure_tracer_returns_active_tracer(self):
        import src.observability as obs

        original = obs._tracer
        try:
            with tempfile.TemporaryDirectory() as tmp:
                tracer = configure_tracer(Path(tmp))
                self.assertIsInstance(tracer, TracerDirect)
                self.assertIsInstance(get_tracer(), TracerDirect)
        finally:
            obs._tracer = original  # restore NullTracer

    def test_configure_tracer_uses_default_logs_dir(self):
        """configure_tracer() without args targets logs/traces.jsonl."""
        import src.observability as obs

        original = obs._tracer
        try:
            tracer = configure_tracer()
            self.assertTrue(str(tracer._writer.output_path).endswith("traces.jsonl"))
        finally:
            obs._tracer = original


# ===========================================================================
# 9. Router instrumentation (integration-style)
# ===========================================================================


class TestRouterInstrumentation(unittest.TestCase):
    """Verify that LLMRouter._build_response() triggers tracer.record_llm_response()."""

    def test_build_response_calls_record_llm_response(self):
        """Mock the tracer and assert it is called from within _build_response."""
        from src.llm.router import LLMRouter

        mock_tracer = MagicMock()
        with patch("src.observability.get_tracer", return_value=mock_tracer):
            # Build a minimal mock completion object
            mock_choice = MagicMock()
            mock_choice.message.content = "hello"
            mock_completion = MagicMock()
            mock_completion.choices = [mock_choice]
            mock_completion.model = "test-model"
            mock_completion.usage.prompt_tokens = 10
            mock_completion.usage.completion_tokens = 5

            # We need a router instance to call _build_response
            from src.llm.client import ProviderConfig

            router = LLMRouter(
                primary_config=ProviderConfig(
                    name="test", base_url="http://localhost:1234/v1", api_key="x"
                ),
                primary_model="test-model",
            )
            response = router._build_response(
                mock_completion, provider="test", latency_ms=100, retry_count=0
            )

        # Tracer should have been called with the LLMResponse
        mock_tracer.record_llm_response.assert_called_once_with(response)
        self.assertEqual(response.input_tokens, 10)
        self.assertEqual(response.output_tokens, 5)


if __name__ == "__main__":
    unittest.main()
