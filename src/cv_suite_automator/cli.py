"""Installed command-line entry point for CV Suite automation."""

from __future__ import annotations

import runpy


def main() -> None:
    """Run the package's interactive automation workflow."""
    runpy.run_module("cv_suite_automator.__main__", run_name="__main__")
