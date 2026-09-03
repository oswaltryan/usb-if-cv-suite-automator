"""Check project-version consistency between pyproject.toml and uv.lock."""

from __future__ import annotations

import argparse
import sys
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PROJECT_NAME = "cv-suite-automator"


def versions() -> tuple[str, str]:
    with (ROOT / "pyproject.toml").open("rb") as stream:
        project = tomllib.load(stream)
    with (ROOT / "uv.lock").open("rb") as stream:
        lock = tomllib.load(stream)
    project_version = project["project"]["version"]
    matches = [
        package
        for package in lock["package"]
        if package["name"] == PROJECT_NAME and package.get("source", {}).get("editable") == "."
    ]
    if len(matches) != 1:
        raise RuntimeError(f"Expected one editable {PROJECT_NAME!r} entry in uv.lock")
    return project_version, matches[0]["version"]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("check", "read"))
    command = parser.parse_args(argv).command
    try:
        project_version, lock_version = versions()
    except (OSError, KeyError, tomllib.TOMLDecodeError, RuntimeError) as exc:
        print(f"Version check failed: {exc}", file=sys.stderr)
        return 1
    if command == "read":
        print(project_version)
        return 0
    if project_version != lock_version:
        print(
            f"Version mismatch: pyproject.toml={project_version}, uv.lock={lock_version}",
            file=sys.stderr,
        )
        return 1
    print(f"Project version {project_version} is consistent with uv.lock")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
