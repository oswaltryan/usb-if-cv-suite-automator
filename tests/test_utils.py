import shutil
import uuid
from pathlib import Path

from cv_suite_automator.utils import custom_json_dump, encode_with_inline_lists


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
    payload = {"Windows 11": {"Intel": {"USB2": {"Device Summary": [1, 1]}}}}

    try:
        custom_json_dump(payload, str(destination))
        written = destination.read_text(encoding="utf-8")

        assert '"Device Summary": [1, 1]' in written
        assert "\n    " in written
    finally:
        shutil.rmtree(scratch, ignore_errors=True)
