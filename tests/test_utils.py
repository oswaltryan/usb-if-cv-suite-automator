import shutil
import uuid
from pathlib import Path

import pytest

from cv_suite_automator.utils import custom_json_dump, encode_with_inline_lists, pull_files


def _new_scratch_dir() -> Path:
    root = Path(".test-scratch")
    root.mkdir(exist_ok=True)
    scratch = root / f"case-{uuid.uuid4().hex}"
    scratch.mkdir(parents=True, exist_ok=False)
    return scratch


def test_encode_with_inline_lists_keeps_list_on_one_line() -> None:
    payload = {"Windows 11": {"ASMedia": {"USB3": {"Device Summary": [2, 0, 6]}}}}

    rendered = encode_with_inline_lists(payload)

    assert '"Device Summary": [2, 0, 6]' in rendered
    assert rendered.startswith("{\n")


def test_custom_json_dump_writes_expected_shape() -> None:
    scratch = _new_scratch_dir()
    destination = scratch / "summary.json"
    payload = {"Windows 10": {"Intel": {"USB2": {"Device Summary": [1, 1]}}}}

    try:
        custom_json_dump(payload, str(destination))
        written = destination.read_text(encoding="utf-8")

        assert '"Device Summary": [1, 1]' in written
        assert "\n    " in written
    finally:
        shutil.rmtree(scratch, ignore_errors=True)


def test_pull_files_moves_html_and_cleans_nested_directories() -> None:
    scratch = _new_scratch_dir()
    source = scratch / "source"
    nested = source / "nested"
    nested.mkdir(parents=True)
    (nested / "report.html").write_text("<html>ok</html>", encoding="utf-8")
    (nested / "notes.txt").write_text("ignore", encoding="utf-8")

    destination = scratch / "dest"

    try:
        pull_files(source=str(source), dest=str(destination))

        assert (destination / "report.html").exists()
        assert not nested.exists()
    finally:
        shutil.rmtree(scratch, ignore_errors=True)


def test_pull_files_raises_for_missing_source() -> None:
    scratch = _new_scratch_dir()
    try:
        with pytest.raises(ValueError, match="Source directory does not exist"):
            pull_files(
                source=str(scratch / "does-not-exist"),
                dest=str(scratch / "dest"),
            )
    finally:
        shutil.rmtree(scratch, ignore_errors=True)
