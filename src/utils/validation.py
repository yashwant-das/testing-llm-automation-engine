"""
Input validation utilities for the QA Agent.
"""

import os
import re
from urllib.parse import urlparse


class ValidationError(Exception):
    """Custom exception for validation errors."""

    pass


def validate_url(url: str) -> bool:
    """Validate that a URL is properly formatted and uses http/https.

    Args:
        url: The URL string to validate

    Returns:
        bool: True if valid, False otherwise
    """
    if not url or not isinstance(url, str):
        return False

    try:
        result = urlparse(url.strip())
        return all(
            [
                result.scheme in ["http", "https"],
                result.netloc,
                len(url) <= 2048,  # Reasonable URL length limit
            ]
        )
    except Exception:
        return False


def validate_and_sanitize_url(url: str) -> str:
    """Validate and sanitize a URL.

    Args:
        url: The URL string to validate and sanitize

    Returns:
        str: Sanitized URL string

    Raises:
        ValidationError: If URL is invalid
    """
    if not url:
        raise ValidationError("URL cannot be empty")

    url = url.strip()

    if not validate_url(url):
        raise ValidationError(f"Invalid URL format: {url}. Must be http:// or https://")

    return url


def validate_file_path(file_path: str, allowed_dirs: list = None) -> str:
    """Validate and sanitize a file path to prevent directory traversal.

    Args:
        file_path: The file path to validate
        allowed_dirs: List of allowed directory prefixes (default: tests/generated)

    Returns:
        str: Normalized absolute path

    Raises:
        ValidationError: If path is invalid or outside allowed directories
    """
    if not file_path:
        raise ValidationError("File path cannot be empty")

    if allowed_dirs is None:
        allowed_dirs = ["tests/generated"]

    # Resolve to absolute path
    abs_path = os.path.abspath(file_path)

    # Check if path is within any allowed directory
    is_allowed = False
    for allowed_dir in allowed_dirs:
        allowed_abs = os.path.abspath(allowed_dir)
        try:
            # Check if the path is within the allowed directory
            os.path.commonpath([abs_path, allowed_abs])
            if abs_path.startswith(allowed_abs):
                is_allowed = True
                break
        except ValueError:
            # Paths don't share a common base
            continue

    if not is_allowed:
        raise ValidationError(
            f"File path must be within allowed directories: {allowed_dirs}"
        )

    return abs_path


def validate_description(description: str, max_length: int = 500) -> str:
    """Validate and sanitize a test description/scenario.

    Args:
        description: The description string to validate
        max_length: Maximum allowed length (default: 500)

    Returns:
        str: Sanitized description string

    Raises:
        ValidationError: If description is invalid
    """
    if not description:
        raise ValidationError("Description cannot be empty")

    if not isinstance(description, str):
        raise ValidationError("Description must be a string")

    description = description.strip()

    if len(description) > max_length:
        raise ValidationError(f"Description too long (max {max_length} characters)")

    # Check for potentially dangerous patterns
    dangerous_patterns = [
        r"[<>]",  # HTML tags
        r"\.\./",  # Path traversal attempts
        r"[;&|$]",  # Command injection attempts (backtick removed for technical descriptions)
    ]

    for pattern in dangerous_patterns:
        if re.search(pattern, description):
            raise ValidationError(
                f"Description contains invalid characters: {description[:50]}..."
            )

    return description
