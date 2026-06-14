"""
Browser utility helpers.
"""


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
