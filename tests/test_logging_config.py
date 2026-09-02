import io
import logging
import re
import sys

from cv_suite_automator.logging_config import configure_logging


def test_console_logging_is_timestamped_idempotent_and_includes_tracebacks(
    monkeypatch,
) -> None:
    root = logging.getLogger()
    original_handlers = root.handlers[:]
    original_level = root.level
    original_hook = sys.excepthook
    stream = io.StringIO()

    try:
        root.handlers = []
        monkeypatch.setattr(sys, "stdout", stream)
        configure_logging()
        configure_logging()

        logging.getLogger("cv_suite_automator.test").info("normal message")
        try:
            raise RuntimeError("boom")
        except RuntimeError:
            exception_type, exception, traceback = sys.exc_info()
            sys.excepthook(exception_type, exception, traceback)

        output = stream.getvalue()
        assert len(root.handlers) == 1
        assert re.search(
            r"\[\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}\] normal message",
            output,
        )
        assert "Traceback (most recent call last):" in output
        assert "RuntimeError: boom" in output
    finally:
        for handler in root.handlers:
            if handler not in original_handlers:
                handler.close()
        root.handlers = original_handlers
        root.setLevel(original_level)
        sys.excepthook = original_hook
