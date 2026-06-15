# Testing Guide

> How tests are structured and how to run them.

---

## Test Architecture

The project has 556 Python unit tests across 16 files. All tests run without a live LLM, live browser, or network connection.

| File | What it tests | Key pattern |
| --- | --- | --- |
| `unit_test_schemas.py` | Pydantic schema validation and coercion | Model construction, field defaults, validators |
| `unit_test_healing.py` | Healing pipeline end-to-end | Mocked LLMRouter, mocked subprocess |
| `unit_test_classification.py` | Heuristic failure classifier | Pure function — no mocks needed |
| `unit_test_fixer.py` | String repair logic | Pure function — fixture code strings |
| `unit_test_ast_repair.py` | AST repair pipeline | Real Node.js subprocess (requires Node.js) |
| `unit_test_llm.py` | LLM router, client, registry, policies | Mocked OpenAI client |
| `unit_test_json.py` | JSON extraction utilities | String inputs |
| `unit_test_validation.py` | Input validation | Edge cases, invalid inputs |
| `unit_test_context.py` | Context collection modules | Mocked Playwright page |
| `unit_test_observability.py` | Tracer, writer, spans | Real file I/O (temp directory) |
| `unit_test_explainability.py` | HealingDecision provenance fields | Schema, round-trip, markdown rendering |
| `unit_test_evaluation.py` | Benchmark runners and evaluators | Pure functions + fixture datasets |
| `unit_test_provenance.py` | GenerationDecision and VisionDecision to_markdown() | Schema construction, markdown output |
| `unit_test_information_architecture.py` | Workbench service — system overview, artifact listing | workbench_service functions |
| `unit_test_visibility.py` | Evidence rendering in decision reports | Context inspector, timeline output |
| `unit_test_workbench_eval.py` | Benchmark report saving and display in workbench | workbench_service evaluation functions |

---

## Running Tests

```bash
# All unit tests (fastest — no external deps)
uv run python -m pytest tests/unit_test_*.py -q

# Single file with verbose output
uv run python -m pytest tests/unit_test_healing.py -v

# Specific test class
uv run python -m pytest tests/unit_test_healing.py::TestAnalyzeAndPlan -v

# With test output (captured by default)
uv run python -m pytest tests/unit_test_schemas.py -v -s

# Run npm test suite (Playwright integration)
npm run test

# All checks (lint + unit tests + Playwright)
npm run lint && uv run python -m pytest tests/unit_test_*.py -q && npm run test
```

---

## Mocking Pattern — LLM Router

Every test that calls into the healing pipeline mocks the LLM router:

```python
from unittest.mock import MagicMock, patch

@patch("src.healing.planner.get_default_router")
@patch("src.healing.planner.load_prompt", return_value="Heal {failure_type} {confidence} {reason}")
def test_returns_decision(self, _mock_prompt, mock_get_router):
    mock_router = MagicMock()
    mock_router.complete_primary.return_value = MagicMock(
        content='{"failure_type":"TIMEOUT","failure_summary":"Timed out",...}',
        model_used="mock-model",
        input_tokens=100,
        output_tokens=50,
        latency_ms=500,
        retry_count=0,
    )
    mock_get_router.return_value = mock_router

    decision = analyze_and_plan("test.spec.ts", "code", evidence)
    self.assertIsInstance(decision, HealingDecision)
```

The `model_used` attribute must be set on the mock response because the planner passes it to `HealingDecision.from_analysis()`.

---

## Mocking Pattern — Playwright Browser

Context collection tests mock the Playwright `page` object:

```python
from unittest.mock import MagicMock, AsyncMock

page = MagicMock()
page.content.return_value = "<html><body>...</body></html>"
page.accessibility.snapshot.return_value = {
    "role": "document",
    "children": [{"role": "button", "name": "Login"}]
}
# ... test collect_dom(page), collect_accessibility_tree(page), etc.
```

No browser is launched. No network calls are made.

---

## Test Isolation — Observability

Observability tests use temporary directories to avoid polluting `logs/traces.jsonl`:

```python
import tempfile
from pathlib import Path
from src.observability.writer import TraceWriter

with tempfile.TemporaryDirectory() as tmpdir:
    writer = TraceWriter(Path(tmpdir) / "traces.jsonl")
    writer.write_span(some_span)
    spans = writer.read_all()
    assert len(spans) == 1
```

The `TraceWriter` creates the parent directory on first write — it does not need pre-existing directories.

---

## Test Isolation — Thread-Local State

Tests that call `Tracer.start_session()` must clean up `_thread_local.session` in `tearDown`:

```python
from src.observability.tracer import _thread_local

class TestTracer(unittest.TestCase):
    def setUp(self):
        _thread_local.session = None

    def tearDown(self):
        _thread_local.session = None
```

Without this, a test that calls `start_session()` but not `end_session()` leaves stale state that causes the next test to see an active session it did not start.

---

## Adding a New Test

1. Add to the appropriate `unit_test_*.py` file, or create a new file following the naming convention
2. Use `unittest.TestCase` subclasses with `test_` method prefix
3. Mock the LLM router if your code calls `get_default_router()`
4. Mock the Playwright page if your code calls `collect_context()` or any context module
5. Run `uv run python -m pytest tests/unit_test_*.py -q` to verify nothing regressed
