"""
Unit tests for src/context/ — Phase 6 Context Collection package.

Covers all seven modules without launching a real browser.  Playwright calls
are mocked via unittest.mock.  Tests are grouped by module.

Run:
    python -m pytest tests/unit_test_context.py -v
"""

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import MagicMock, patch

# ---------------------------------------------------------------------------
# Helpers shared across test classes
# ---------------------------------------------------------------------------


def _make_pw_mocks():
    """Return (mock_pw_ctx_mgr, mock_p, mock_browser, mock_ctx, mock_page).

    Wires up the sync_playwright() context manager chain so that:
        with sync_playwright() as p:
            browser = p.chromium.launch(...)
            ctx = browser.new_context(...)
            page = ctx.new_page()
    all resolve to the returned mocks.
    """
    mock_p = MagicMock()
    mock_browser = MagicMock()
    mock_ctx = MagicMock()
    mock_page = MagicMock()

    mock_pw_ctx_mgr = MagicMock()
    mock_pw_ctx_mgr.__enter__ = MagicMock(return_value=mock_p)
    mock_pw_ctx_mgr.__exit__ = MagicMock(return_value=False)

    mock_p.chromium.launch.return_value = mock_browser
    mock_browser.new_context.return_value = mock_ctx
    mock_ctx.new_page.return_value = mock_page

    return mock_pw_ctx_mgr, mock_p, mock_browser, mock_ctx, mock_page


# ---------------------------------------------------------------------------
# dom.py
# ---------------------------------------------------------------------------


class TestCollectDom(unittest.TestCase):
    def setUp(self):
        from src.context.dom import collect_dom

        self.collect_dom = collect_dom

    def _mock_page(self, html: str) -> MagicMock:
        page = MagicMock()
        page.content.return_value = html
        return page

    def test_strips_script_tags(self):
        page = self._mock_page(
            "<html><body><script>alert(1)</script><p>Hello</p></body></html>"
        )
        result = self.collect_dom(page)
        self.assertNotIn("<script>", result)
        self.assertIn("Hello", result)

    def test_strips_style_tags(self):
        page = self._mock_page(
            "<html><body><style>body{color:red}</style><p>World</p></body></html>"
        )
        result = self.collect_dom(page)
        self.assertNotIn("<style>", result)
        self.assertIn("World", result)

    def test_strips_svg_tags(self):
        page = self._mock_page(
            "<html><body><svg><path d='M0 0'/></svg><p>Content</p></body></html>"
        )
        result = self.collect_dom(page)
        self.assertNotIn("<svg>", result)
        self.assertIn("Content", result)

    def test_respects_max_chars(self):
        page = self._mock_page("<html><body>" + "<p>word</p>" * 1000 + "</body></html>")
        result = self.collect_dom(page, max_chars=100)
        self.assertLessEqual(len(result), 100)

    def test_returns_empty_on_page_error(self):
        page = MagicMock()
        page.content.side_effect = Exception("page closed")
        result = self.collect_dom(page)
        self.assertEqual(result, "")

    def test_returns_empty_for_headless_body(self):
        page = self._mock_page("<html><head><title>No body</title></head></html>")
        result = self.collect_dom(page)
        self.assertEqual(result, "")

    def test_real_page_content(self):
        page = self._mock_page(
            "<html><body><button id='btn'>Click me</button></body></html>"
        )
        result = self.collect_dom(page)
        self.assertIn("Click me", result)


# ---------------------------------------------------------------------------
# accessibility.py
# ---------------------------------------------------------------------------


class TestFormatAccessibilitySnapshot(unittest.TestCase):
    def setUp(self):
        from src.context.accessibility import format_accessibility_snapshot

        self.fmt = format_accessibility_snapshot

    def test_formats_simple_node(self):
        node = {"role": "button", "name": "Submit", "children": []}
        result = self.fmt(node)
        self.assertIn("[button] Submit", result)

    def test_formats_node_without_name(self):
        node = {"role": "WebArea", "children": []}
        result = self.fmt(node)
        self.assertIn("[WebArea]", result)
        self.assertNotIn("None", result)

    def test_indents_children(self):
        node = {
            "role": "WebArea",
            "name": "Page",
            "children": [{"role": "button", "name": "OK", "children": []}],
        }
        result = self.fmt(node)
        lines = result.split("\n")
        root_line = next(ln for ln in lines if "WebArea" in ln)
        child_line = next(ln for ln in lines if "button" in ln)
        root_indent = len(root_line) - len(root_line.lstrip())
        child_indent = len(child_line) - len(child_line.lstrip())
        self.assertGreater(child_indent, root_indent)

    def test_deep_nesting(self):
        node = {
            "role": "main",
            "children": [
                {
                    "role": "section",
                    "children": [{"role": "button", "name": "Deep", "children": []}],
                }
            ],
        }
        result = self.fmt(node)
        self.assertIn("[button] Deep", result)


class TestCollectAccessibilityTree(unittest.TestCase):
    def setUp(self):
        from src.context.accessibility import collect_accessibility_tree

        self.collect = collect_accessibility_tree

    def test_returns_string_on_success(self):
        page = MagicMock()
        page.accessibility.snapshot.return_value = {
            "role": "button",
            "name": "OK",
            "children": [],
        }
        result = self.collect(page)
        self.assertIn("[button] OK", result)

    def test_returns_empty_when_snapshot_is_none(self):
        page = MagicMock()
        page.accessibility.snapshot.return_value = None
        result = self.collect(page)
        self.assertEqual(result, "")

    def test_returns_empty_on_exception(self):
        page = MagicMock()
        page.accessibility.snapshot.side_effect = Exception("not available")
        result = self.collect(page)
        self.assertEqual(result, "")


# ---------------------------------------------------------------------------
# locator_candidates.py
# ---------------------------------------------------------------------------


class TestExtractLocatorCandidates(unittest.TestCase):
    def setUp(self):
        from src.context.locator_candidates import extract_locator_candidates

        self.extract = extract_locator_candidates

    def _snapshot(self, role: str, name: str, children=None):
        return {"role": role, "name": name, "children": children or []}

    def test_emits_button_candidate(self):
        snap = self._snapshot("button", "Submit")
        result = self.extract(snap)
        self.assertIn("getByRole('button', { name: 'Submit' })", result)

    def test_emits_link_candidate(self):
        snap = self._snapshot("link", "Home")
        result = self.extract(snap)
        self.assertIn("getByRole('link', { name: 'Home' })", result)

    def test_emits_textbox_candidate(self):
        snap = self._snapshot("textbox", "Username")
        result = self.extract(snap)
        self.assertIn("getByRole('textbox', { name: 'Username' })", result)

    def test_skips_role_without_name(self):
        snap = self._snapshot("button", "")
        result = self.extract(snap)
        self.assertEqual(result, [])

    def test_skips_non_interactive_role(self):
        snap = self._snapshot("paragraph", "Some text")
        result = self.extract(snap)
        self.assertEqual(result, [])

    def test_walks_children(self):
        snap = {
            "role": "WebArea",
            "name": "",
            "children": [
                {"role": "button", "name": "Cancel", "children": []},
                {"role": "link", "name": "Back", "children": []},
            ],
        }
        result = self.extract(snap)
        self.assertIn("getByRole('button', { name: 'Cancel' })", result)
        self.assertIn("getByRole('link', { name: 'Back' })", result)

    def test_respects_max_count(self):
        snap = {
            "role": "WebArea",
            "name": "",
            "children": [
                {"role": "button", "name": f"Btn {i}", "children": []}
                for i in range(30)
            ],
        }
        result = self.extract(snap, max_count=5)
        self.assertLessEqual(len(result), 5)

    def test_escapes_single_quotes_in_name(self):
        snap = self._snapshot("button", "Don't click")
        result = self.extract(snap)
        # Should not produce broken JS
        self.assertIn("\\'", result[0])

    def test_heading_is_included(self):
        snap = self._snapshot("heading", "Welcome")
        result = self.extract(snap)
        self.assertIn("getByRole('heading', { name: 'Welcome' })", result)


# ---------------------------------------------------------------------------
# console.py
# ---------------------------------------------------------------------------


class TestAttachConsoleListener(unittest.TestCase):
    def setUp(self):
        from src.context.console import attach_console_listener

        self.attach = attach_console_listener

    def _attach_and_fire(self, msg_type: str, msg_text: str):
        """Attach listener to a mock page, then fire a console event."""
        page = MagicMock()
        handler_ref = {}

        def capture_on(event, handler):
            handler_ref[event] = handler

        page.on.side_effect = capture_on
        errors = self.attach(page)

        mock_msg = MagicMock()
        mock_msg.type = msg_type
        mock_msg.text = msg_text
        handler_ref["console"](mock_msg)
        return errors

    def test_registers_on_console_event(self):
        page = MagicMock()
        self.attach(page)
        page.on.assert_called_once()
        self.assertEqual(page.on.call_args[0][0], "console")

    def test_captures_error_messages(self):
        errors = self._attach_and_fire("error", "Uncaught TypeError")
        self.assertEqual(errors, ["[ERROR] Uncaught TypeError"])

    def test_captures_warning_messages(self):
        errors = self._attach_and_fire("warning", "Deprecated API")
        self.assertEqual(errors, ["[WARNING] Deprecated API"])

    def test_ignores_log_messages(self):
        errors = self._attach_and_fire("log", "Regular log output")
        self.assertEqual(errors, [])

    def test_ignores_info_messages(self):
        errors = self._attach_and_fire("info", "Information")
        self.assertEqual(errors, [])

    def test_returns_mutable_list(self):
        page = MagicMock()
        result = self.attach(page)
        self.assertIsInstance(result, list)


# ---------------------------------------------------------------------------
# network.py
# ---------------------------------------------------------------------------


class TestAttachNetworkListener(unittest.TestCase):
    def setUp(self):
        from src.context.network import attach_network_listener

        self.attach = attach_network_listener

    def _attach_and_fire(self, method: str, url: str, failure: str):
        """Attach listener to a mock page, then fire a requestfailed event."""
        page = MagicMock()
        handler_ref = {}

        def capture_on(event, handler):
            handler_ref[event] = handler

        page.on.side_effect = capture_on
        failures = self.attach(page)

        mock_request = MagicMock()
        mock_request.method = method
        mock_request.url = url
        mock_request.failure = failure
        handler_ref["requestfailed"](mock_request)
        return failures

    def test_registers_on_requestfailed_event(self):
        page = MagicMock()
        self.attach(page)
        page.on.assert_called_once()
        self.assertEqual(page.on.call_args[0][0], "requestfailed")

    def test_captures_get_failures(self):
        failures = self._attach_and_fire(
            "GET", "https://example.com/api", "net::ERR_CONNECTION_REFUSED"
        )
        self.assertEqual(
            failures,
            ["GET https://example.com/api [net::ERR_CONNECTION_REFUSED]"],
        )

    def test_captures_post_failures(self):
        failures = self._attach_and_fire(
            "POST", "https://example.com/submit", "net::ERR_TIMED_OUT"
        )
        self.assertIn("POST", failures[0])
        self.assertIn("ERR_TIMED_OUT", failures[0])

    def test_returns_mutable_list(self):
        page = MagicMock()
        result = self.attach(page)
        self.assertIsInstance(result, list)

    def test_handles_none_failure_reason(self):
        page = MagicMock()
        handler_ref = {}

        def capture_on(event, handler):
            handler_ref[event] = handler

        page.on.side_effect = capture_on
        failures = self.attach(page)

        mock_request = MagicMock()
        mock_request.method = "GET"
        mock_request.url = "https://example.com"
        mock_request.failure = None
        handler_ref["requestfailed"](mock_request)
        self.assertIn("unknown", failures[0])


# ---------------------------------------------------------------------------
# screenshot.py
# ---------------------------------------------------------------------------


class TestCaptureFromPage(unittest.TestCase):
    def setUp(self):
        from src.context.screenshot import capture_from_page

        self.capture = capture_from_page

    def test_calls_page_screenshot(self):
        page = MagicMock()
        with TemporaryDirectory() as tmp:
            self.capture(page, Path(tmp), url="https://example.com", tag="test")
        page.screenshot.assert_called_once()

    def test_creates_output_dir(self):
        page = MagicMock()
        with TemporaryDirectory() as tmp:
            new_dir = Path(tmp) / "screenshots"
            self.assertFalse(new_dir.exists())
            self.capture(page, new_dir, url="https://example.com")
            self.assertTrue(new_dir.exists())

    def test_returns_string_path(self):
        page = MagicMock()
        with TemporaryDirectory() as tmp:
            result = self.capture(
                page, Path(tmp), url="https://example.com", tag="view"
            )
        self.assertIsInstance(result, str)
        self.assertTrue(result.endswith(".png"))

    def test_filename_includes_tag(self):
        page = MagicMock()
        with TemporaryDirectory() as tmp:
            result = self.capture(
                page, Path(tmp), url="https://example.com", tag="myview"
            )
        self.assertIn("myview", result)

    def test_filename_includes_domain(self):
        page = MagicMock()
        with TemporaryDirectory() as tmp:
            result = self.capture(page, Path(tmp), url="https://mysite.com/path")
        self.assertIn("mysite", result)

    def test_fallback_domain_when_url_empty(self):
        page = MagicMock()
        with TemporaryDirectory() as tmp:
            result = self.capture(page, Path(tmp), url="")
        self.assertTrue(result.endswith(".png"))


class TestCaptureScreenshot(unittest.TestCase):
    def setUp(self):
        from src.context.screenshot import capture_screenshot

        self.capture = capture_screenshot

    def test_delegates_to_playwright(self):
        mock_ctx_mgr, mock_p, mock_browser, mock_ctx, mock_page = _make_pw_mocks()
        with patch("src.context.screenshot.sync_playwright", return_value=mock_ctx_mgr):
            with TemporaryDirectory() as tmp:
                result = self.capture(
                    "https://example.com", Path(tmp), tag="test", wait_ms=0
                )
        mock_page.goto.assert_called_once()
        mock_page.screenshot.assert_called_once()
        self.assertTrue(result.endswith(".png"))

    def test_creates_output_dir(self):
        mock_ctx_mgr, *_ = _make_pw_mocks()
        with patch("src.context.screenshot.sync_playwright", return_value=mock_ctx_mgr):
            with TemporaryDirectory() as tmp:
                new_dir = Path(tmp) / "caps"
                self.assertFalse(new_dir.exists())
                self.capture("https://example.com", new_dir, wait_ms=0)
                self.assertTrue(new_dir.exists())

    def test_closes_browser(self):
        mock_ctx_mgr, mock_p, mock_browser, *_ = _make_pw_mocks()
        with patch("src.context.screenshot.sync_playwright", return_value=mock_ctx_mgr):
            with TemporaryDirectory() as tmp:
                self.capture("https://example.com", Path(tmp), wait_ms=0)
        mock_browser.close.assert_called_once()


# ---------------------------------------------------------------------------
# collector.py
# ---------------------------------------------------------------------------


class TestCollectContext(unittest.TestCase):
    """Tests for the unified context collector."""

    def setUp(self):
        from src.context.collector import collect_context

        self.collect = collect_context

    def _mock_page_defaults(self, page: MagicMock) -> None:
        """Set sensible defaults on a mock page."""
        page.content.return_value = "<html><body><button>Submit</button></body></html>"
        page.accessibility.snapshot.return_value = {
            "role": "WebArea",
            "name": "Page",
            "children": [{"role": "button", "name": "Submit", "children": []}],
        }
        # on() captures handlers; subsequent calls append to captured list
        page.on.return_value = None

    def test_returns_context_snapshot(self):
        from schemas.artifacts import ContextSnapshot

        mock_ctx_mgr, _, _, _, mock_page = _make_pw_mocks()
        self._mock_page_defaults(mock_page)
        with patch("src.context.collector.sync_playwright", return_value=mock_ctx_mgr):
            result = self.collect("https://example.com", wait_ms=0)
        self.assertIsInstance(result, ContextSnapshot)
        self.assertEqual(result.url, "https://example.com")

    def test_collects_html(self):
        mock_ctx_mgr, _, _, _, mock_page = _make_pw_mocks()
        self._mock_page_defaults(mock_page)
        with patch("src.context.collector.sync_playwright", return_value=mock_ctx_mgr):
            result = self.collect("https://example.com", capture_html=True, wait_ms=0)
        self.assertIsNotNone(result.html)
        self.assertIn("Submit", result.html)

    def test_collects_accessibility_tree(self):
        mock_ctx_mgr, _, _, _, mock_page = _make_pw_mocks()
        self._mock_page_defaults(mock_page)
        with patch("src.context.collector.sync_playwright", return_value=mock_ctx_mgr):
            result = self.collect("https://example.com", capture_a11y=True, wait_ms=0)
        self.assertIsNotNone(result.accessibility_tree)
        self.assertIn("[button] Submit", result.accessibility_tree)

    def test_extracts_locator_candidates(self):
        mock_ctx_mgr, _, _, _, mock_page = _make_pw_mocks()
        self._mock_page_defaults(mock_page)
        with patch("src.context.collector.sync_playwright", return_value=mock_ctx_mgr):
            result = self.collect("https://example.com", capture_a11y=True, wait_ms=0)
        self.assertIn(
            "getByRole('button', { name: 'Submit' })",
            result.locator_candidates,
        )

    def test_skip_html_when_disabled(self):
        mock_ctx_mgr, _, _, _, mock_page = _make_pw_mocks()
        self._mock_page_defaults(mock_page)
        with patch("src.context.collector.sync_playwright", return_value=mock_ctx_mgr):
            result = self.collect(
                "https://example.com",
                capture_html=False,
                capture_a11y=False,
                wait_ms=0,
            )
        self.assertIsNone(result.html)

    def test_skip_a11y_when_disabled(self):
        mock_ctx_mgr, _, _, _, mock_page = _make_pw_mocks()
        self._mock_page_defaults(mock_page)
        with patch("src.context.collector.sync_playwright", return_value=mock_ctx_mgr):
            result = self.collect(
                "https://example.com",
                capture_html=False,
                capture_a11y=False,
                wait_ms=0,
            )
        self.assertIsNone(result.accessibility_tree)
        self.assertEqual(result.locator_candidates, [])

    def test_returns_partial_snapshot_on_navigation_error(self):
        mock_ctx_mgr, _, _, _, mock_page = _make_pw_mocks()
        mock_page.goto.side_effect = Exception("net::ERR_NAME_NOT_RESOLVED")
        with patch("src.context.collector.sync_playwright", return_value=mock_ctx_mgr):
            result = self.collect("https://nonexistent.invalid", wait_ms=0)
        # URL is always set; HTML/a11y are None
        self.assertEqual(result.url, "https://nonexistent.invalid")
        self.assertIsNone(result.html)
        self.assertIsNone(result.accessibility_tree)

    def test_returns_partial_snapshot_on_playwright_error(self):
        mock_ctx_mgr = MagicMock()
        mock_ctx_mgr.__enter__ = MagicMock(side_effect=Exception("playwright crash"))
        mock_ctx_mgr.__exit__ = MagicMock(return_value=False)
        with patch("src.context.collector.sync_playwright", return_value=mock_ctx_mgr):
            result = self.collect("https://example.com", wait_ms=0)
        self.assertEqual(result.url, "https://example.com")

    def test_closes_browser_on_success(self):
        mock_ctx_mgr, _, mock_browser, _, mock_page = _make_pw_mocks()
        self._mock_page_defaults(mock_page)
        with patch("src.context.collector.sync_playwright", return_value=mock_ctx_mgr):
            self.collect("https://example.com", wait_ms=0)
        mock_browser.close.assert_called_once()

    def test_console_listener_attached_before_goto(self):
        """Verify page.on('console', ...) is called before page.goto()."""
        mock_ctx_mgr, _, _, _, mock_page = _make_pw_mocks()
        self._mock_page_defaults(mock_page)
        call_order = []
        mock_page.on.side_effect = lambda ev, _h: call_order.append(f"on:{ev}")
        mock_page.goto.side_effect = lambda *a, **kw: call_order.append("goto")
        with patch("src.context.collector.sync_playwright", return_value=mock_ctx_mgr):
            self.collect(
                "https://example.com",
                capture_console=True,
                wait_ms=0,
            )
        console_idx = next(
            (i for i, v in enumerate(call_order) if v == "on:console"), -1
        )
        goto_idx = next((i for i, v in enumerate(call_order) if v == "goto"), -1)
        self.assertGreater(
            goto_idx, console_idx, "console listener must be before goto"
        )

    def test_network_listener_attached_before_goto(self):
        """Verify page.on('requestfailed', ...) is called before page.goto()."""
        mock_ctx_mgr, _, _, _, mock_page = _make_pw_mocks()
        self._mock_page_defaults(mock_page)
        call_order = []
        mock_page.on.side_effect = lambda ev, _h: call_order.append(f"on:{ev}")
        mock_page.goto.side_effect = lambda *a, **kw: call_order.append("goto")
        with patch("src.context.collector.sync_playwright", return_value=mock_ctx_mgr):
            self.collect(
                "https://example.com",
                capture_network=True,
                wait_ms=0,
            )
        net_idx = next(
            (i for i, v in enumerate(call_order) if v == "on:requestfailed"), -1
        )
        goto_idx = next((i for i, v in enumerate(call_order) if v == "goto"), -1)
        self.assertGreater(goto_idx, net_idx, "network listener must be before goto")

    def test_no_listeners_when_disabled(self):
        mock_ctx_mgr, _, _, _, mock_page = _make_pw_mocks()
        self._mock_page_defaults(mock_page)
        with patch("src.context.collector.sync_playwright", return_value=mock_ctx_mgr):
            self.collect(
                "https://example.com",
                capture_console=False,
                capture_network=False,
                wait_ms=0,
            )
        mock_page.on.assert_not_called()


# ---------------------------------------------------------------------------
# schemas/artifacts.py — ContextSnapshot properties
# ---------------------------------------------------------------------------


class TestContextSnapshotProperties(unittest.TestCase):
    def setUp(self):
        from schemas.artifacts import ContextSnapshot

        self.ContextSnapshot = ContextSnapshot

    def test_is_empty_when_no_html_or_a11y(self):
        snap = self.ContextSnapshot(url="https://example.com")
        self.assertTrue(snap.is_empty)

    def test_not_empty_when_html_present(self):
        snap = self.ContextSnapshot(url="https://example.com", html="<p>hi</p>")
        self.assertFalse(snap.is_empty)

    def test_not_empty_when_a11y_present(self):
        snap = self.ContextSnapshot(
            url="https://example.com", accessibility_tree="[button] OK"
        )
        self.assertFalse(snap.is_empty)

    def test_has_html(self):
        snap = self.ContextSnapshot(url="https://example.com", html="<p>hi</p>")
        self.assertTrue(snap.has_html)

    def test_has_a11y_tree(self):
        snap = self.ContextSnapshot(
            url="https://example.com", accessibility_tree="[button] OK"
        )
        self.assertTrue(snap.has_a11y_tree)

    def test_console_errors_defaults_to_empty_list(self):
        snap = self.ContextSnapshot(url="https://example.com")
        self.assertEqual(snap.console_errors, [])

    def test_network_errors_defaults_to_empty_list(self):
        snap = self.ContextSnapshot(url="https://example.com")
        self.assertEqual(snap.network_errors, [])

    def test_locator_candidates_defaults_to_empty_list(self):
        snap = self.ContextSnapshot(url="https://example.com")
        self.assertEqual(snap.locator_candidates, [])


# ---------------------------------------------------------------------------
# schemas/healing.py — Evidence.from_context_snapshot
# ---------------------------------------------------------------------------


class TestEvidenceFromContextSnapshot(unittest.TestCase):
    def setUp(self):
        from schemas.artifacts import ContextSnapshot
        from schemas.healing import Evidence

        self.Evidence = Evidence
        self.ContextSnapshot = ContextSnapshot

    def _snapshot(self, **kwargs):
        return self.ContextSnapshot(url="https://example.com", **kwargs)

    def test_populates_error_log(self):
        snap = self._snapshot()
        ev = self.Evidence.from_context_snapshot("Error: test failed", snap)
        self.assertEqual(ev.error_log, "Error: test failed")

    def test_uses_snapshot_html_as_dom_snippet(self):
        snap = self._snapshot(html="<p>hello</p>")
        ev = self.Evidence.from_context_snapshot("err", snap)
        self.assertEqual(ev.dom_snippet, "<p>hello</p>")

    def test_uses_snapshot_screenshot_path(self):
        snap = self._snapshot(screenshot_path="/tmp/screen.png")
        ev = self.Evidence.from_context_snapshot("err", snap)
        self.assertEqual(ev.screenshot_path, "/tmp/screen.png")

    def test_explicit_screenshot_path_takes_precedence(self):
        snap = self._snapshot(screenshot_path="/tmp/snap.png")
        ev = self.Evidence.from_context_snapshot(
            "err", snap, screenshot_path="/tmp/override.png"
        )
        self.assertEqual(ev.screenshot_path, "/tmp/override.png")

    def test_copies_console_errors(self):
        snap = self._snapshot(console_errors=["[ERROR] Foo", "[WARNING] Bar"])
        ev = self.Evidence.from_context_snapshot("err", snap)
        self.assertEqual(ev.console_errors, ["[ERROR] Foo", "[WARNING] Bar"])

    def test_copies_network_errors(self):
        snap = self._snapshot(
            network_errors=["GET https://api.example.com [net::ERR_FAILED]"]
        )
        ev = self.Evidence.from_context_snapshot("err", snap)
        self.assertEqual(
            ev.network_errors,
            ["GET https://api.example.com [net::ERR_FAILED]"],
        )

    def test_copies_accessibility_tree(self):
        snap = self._snapshot(accessibility_tree="[button] OK")
        ev = self.Evidence.from_context_snapshot("err", snap)
        self.assertEqual(ev.accessibility_tree, "[button] OK")

    def test_copies_locator_candidates(self):
        snap = self._snapshot(
            locator_candidates=["getByRole('button', { name: 'Submit' })"]
        )
        ev = self.Evidence.from_context_snapshot("err", snap)
        self.assertIn("getByRole('button', { name: 'Submit' })", ev.locator_candidates)

    def test_handles_empty_snapshot(self):
        snap = self._snapshot()
        ev = self.Evidence.from_context_snapshot("err", snap)
        self.assertIsNone(ev.dom_snippet)
        self.assertEqual(ev.console_errors, [])
        self.assertEqual(ev.network_errors, [])
        self.assertIsNone(ev.accessibility_tree)
        self.assertEqual(ev.locator_candidates, [])


if __name__ == "__main__":
    unittest.main()
