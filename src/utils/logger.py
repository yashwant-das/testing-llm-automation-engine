"""
Colored, compact logging for the AI Engineering Workbench.

Usage (call once at startup before any other imports):
    from src.utils.logger import init_logging
    init_logging()

All other modules continue to use logging.getLogger(__name__) unchanged.
"""

import logging
import os
import sys

_RESET = "\033[0m"
_DIM = "\033[2m"
_YELLOW = "\033[33m"
_RED = "\033[31m"
_BOLD_RED = "\033[1;31m"

_LEVEL_STYLES: dict[int, tuple[str, str]] = {
    logging.DEBUG: (_DIM, "DEBUG"),
    logging.INFO: ("", "INFO "),
    logging.WARNING: (_YELLOW, "WARN "),
    logging.ERROR: (_RED, "ERROR"),
    logging.CRITICAL: (_BOLD_RED, "CRIT "),
}

_NOISY_LOGGERS = (
    "httpx",
    "openai._base_client",
    "gradio",
    "uvicorn.access",
    "multipart",
)


class _ColoredFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        color, label = _LEVEL_STYLES.get(record.levelno, ("", record.levelname[:5]))

        # Strip leading "src." so "src.llm.router" → "llm.router"
        name = record.name
        if name.startswith("src."):
            name = name[4:]

        ts = self.formatTime(record, "%H:%M:%S")
        msg = record.getMessage()

        if record.exc_info:
            msg = msg + "\n" + self.formatException(record.exc_info)

        if color:
            return f"{_DIM}{ts}{_RESET} {color}[{label}]{_RESET} {name} — {msg}"
        return f"{_DIM}{ts}{_RESET} [{label}] {name} — {msg}"


def init_logging() -> None:
    """Configure root logger with color output and silence third-party noise."""
    level_name = os.getenv("LOG_LEVEL", "INFO").upper()
    level = getattr(logging, level_name, logging.INFO)

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(_ColoredFormatter())

    root = logging.getLogger()
    root.setLevel(level)
    # Replace any handlers already attached (e.g. from basicConfig)
    root.handlers.clear()
    root.addHandler(handler)

    for name in _NOISY_LOGGERS:
        logging.getLogger(name).setLevel(logging.WARNING)
