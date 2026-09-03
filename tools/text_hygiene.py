"""Check repository text hygiene without rewriting files."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Iterable

MARKDOWN_SUFFIXES = {".md", ".markdown"}


def check_file(path: Path) -> list[str]:
    if not path.exists():
        return []
    data = path.read_bytes()
    failures: list[str] = []
    if b"\r" in data:
        failures.append(f"{path}: contains CR or CRLF line endings; expected LF")
    if data and not data.endswith(b"\n"):
        failures.append(f"{path}: missing final newline")
    elif data.endswith(b"\n\n"):
        failures.append(f"{path}: has more than one newline at end of file")
    preserve_markdown_breaks = path.suffix.lower() in MARKDOWN_SUFFIXES
    for line_number, line in enumerate(data.splitlines(), start=1):
        content = line.rstrip(b"\r")
        trailing = content[len(content.rstrip(b" \t")) :]
        if trailing and not (preserve_markdown_breaks and trailing == b"  "):
            failures.append(f"{path}:{line_number}: trailing whitespace")
    return failures


def check_files(paths: Iterable[Path]) -> list[str]:
    return [failure for path in paths for failure in check_file(path)]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("filenames", nargs="*", type=Path)
    failures = check_files(parser.parse_args(argv).filenames)
    if failures:
        print("\n".join(failures))
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
