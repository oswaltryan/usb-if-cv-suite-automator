"""Run the deterministic local pre-push and CI quality gate."""

from __future__ import annotations

import platform
import subprocess
import sys
from pathlib import Path
from typing import Sequence

ROOT = Path(__file__).resolve().parents[1]
SYNC_COMMAND = ("uv", "sync", "--locked", "--dev")
VERSION_COMMANDS = (
    ("uv", "--version"),
    ("uv", "run", "--no-sync", "pre-commit", "--version"),
    ("uv", "run", "--no-sync", "ruff", "--version"),
    ("uv", "run", "--no-sync", "mypy", "--version"),
    ("uv", "run", "--no-sync", "pytest", "--version"),
)
CHECK_COMMAND = (
    "uv",
    "run",
    "--no-sync",
    "pre-commit",
    "run",
    "--all-files",
    "--hook-stage",
    "manual",
    "--show-diff-on-failure",
    "--color=always",
)


def _run(command: Sequence[str]) -> int:
    print(f"+ {' '.join(command)}", flush=True)
    try:
        result = subprocess.run(list(command), cwd=ROOT, check=False)
    except FileNotFoundError:
        print(f"Required command is not installed: {command[0]}", file=sys.stderr)
        return 127
    return result.returncode


def _working_tree_status() -> tuple[int, str]:
    try:
        result = subprocess.run(
            ["git", "status", "--porcelain", "--untracked-files=all"],
            cwd=ROOT,
            check=False,
            capture_output=True,
            text=True,
        )
    except FileNotFoundError:
        return 127, "git is not installed"
    return result.returncode, result.stdout.strip()


def _require_clean_tree(phase: str) -> bool:
    status_code, status = _working_tree_status()
    if status_code:
        print(f"Unable to inspect the working tree during {phase}.", file=sys.stderr)
        return False
    if status:
        print(f"Quality gate requires a clean working tree {phase}:\n{status}", file=sys.stderr)
        return False
    return True


def run_quality_gate() -> int:
    if not _require_clean_tree("before checks"):
        return 1
    print(f"Platform: {platform.platform()}")
    print(f"Python: {sys.version.split()[0]}")
    if return_code := _run(SYNC_COMMAND):
        return return_code
    for command in VERSION_COMMANDS:
        if return_code := _run(command):
            return return_code
    result = _run(CHECK_COMMAND)
    if not _require_clean_tree("after checks"):
        return 1
    return result


def main() -> int:
    return run_quality_gate()


if __name__ == "__main__":
    raise SystemExit(main())
