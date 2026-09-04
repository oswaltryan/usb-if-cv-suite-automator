"""Installed command-line entry point for CV Suite automation."""

from __future__ import annotations

import argparse
import runpy
import sys
from collections.abc import Sequence


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="usb-if",
        description="Run the interactive USB-IF CV Suite automation workflow.",
    )
    parser.add_argument(
        "chipset",
        metavar="CHIPSET",
        help="bridge controller chipset used to identify the test session",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> None:
    """Run the package's interactive automation workflow."""
    arguments = _parser().parse_args(argv)
    original_argv = sys.argv
    sys.argv = [original_argv[0], arguments.chipset]
    try:
        runpy.run_module("cv_suite_automator.__main__", run_name="__main__")
    finally:
        sys.argv = original_argv
