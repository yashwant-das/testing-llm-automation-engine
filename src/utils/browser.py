"""
Browser automation utilities for page context extraction.

``fetch_page_context`` is deprecated as of Phase 6.
Use ``src.context.collect_context`` instead.

``extract_domain`` is retained (not deprecated) — it is used by vision_service
and other modules that need a filename-safe domain string.
"""

import warnings


def extract_domain(url: str) -> str:
    """Extract a clean domain name from a URL for use in filenames.

    Args:
        url: URL string.

    Returns:
        Clean domain name (e.g. ``"example"`` from ``"https://www.example.com"``).
    """
    from urllib.parse import urlparse

    try:
        netloc = urlparse(url).netloc
        domain = netloc.replace("www.", "").split(".")[0]
        return domain if domain else "test"
    except Exception:
        return "test"


def fetch_page_context(url: str, max_chars: int = 30000) -> str:
    """Fetch and clean HTML content from a web page.

    .. deprecated:: Phase 6
        Use :func:`src.context.collect_context` instead.  This shim delegates
        to ``collect_context`` and will be removed in Phase 7.

    Args:
        url:      Validated URL string.
        max_chars: Maximum characters to return (default: 30000).

    Returns:
        Cleaned HTML body as a string, or an error message if fetch fails.
    """
    warnings.warn(
        "fetch_page_context() is deprecated; use src.context.collect_context() instead.",
        DeprecationWarning,
        stacklevel=2,
    )
    try:
        from src.context import collect_context

        snapshot = collect_context(
            url,
            capture_html=True,
            capture_a11y=False,
            capture_console=False,
            capture_network=False,
            max_html_chars=max_chars,
        )
        if not snapshot.html:
            return f"Error: Failed to fetch page context from {url}"
        return snapshot.html
    except Exception as exc:
        return f"Error scanning page: {exc}"
