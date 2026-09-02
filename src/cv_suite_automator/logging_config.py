"""Small, process-wide console logging configuration."""

from __future__ import annotations

import logging
import sys
from types import TracebackType


_HANDLER_MARKER = "cv_suite_automator_console"


def _log_unhandled_exception(
    exception_type: type[BaseException],
    exception: BaseException,
    traceback: TracebackType | None,
) -> None:
    if issubclass(exception_type, KeyboardInterrupt):
        sys.__excepthook__(exception_type, exception, traceback)
        return
    logging.getLogger("cv_suite_automator").critical(
        "Unhandled exception",
        exc_info=(exception_type, exception, traceback),
    )


def configure_logging() -> None:
    """Configure timestamped stdout logging exactly once."""
    root = logging.getLogger()
    if not any(
        getattr(handler, "name", None) == _HANDLER_MARKER
        for handler in root.handlers
    ):
        handler = logging.StreamHandler(sys.stdout)
        handler.name = _HANDLER_MARKER
        handler.setFormatter(
            logging.Formatter("[%(asctime)s] %(message)s", "%Y-%m-%d %H:%M:%S")
        )
        root.addHandler(handler)
    root.setLevel(logging.INFO)
    sys.excepthook = _log_unhandled_exception
