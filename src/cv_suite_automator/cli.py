"""Installed command-line entry point for CV Suite automation and parsing."""

from __future__ import annotations

import argparse
import runpy
import sys
from collections.abc import Sequence


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="usb-if",
        description="Run USB-IF CV Suite automation, qualification, or results parsing.",
    )
    commands = parser.add_subparsers(
        dest="command",
        metavar="{run,qual,parse}",
        title="commands",
        required=True,
    )

    run_parser = commands.add_parser(
        "run",
        help="run the interactive CV Suite automation workflow",
        description="Run the interactive USB-IF CV Suite automation workflow.",
    )
    run_parser.add_argument(
        "chipset",
        metavar="CHIPSET",
        help="bridge controller chipset used to identify the test session",
    )
    commands.add_parser(
        "qual",
        help="run MSC Tests three times for storage qualification",
        description=(
            "Run MSC Tests three consecutive times using the detected controller and USB3."
        ),
    )
    parse_parser = commands.add_parser(
        "parse",
        help="summarize failures from an existing firmware directory",
        description="Parse exact CV Suite failures for one firmware version.",
    )
    parse_parser.add_argument(
        "directory",
        metavar="DIRECTORY",
        help=(
            "firmware directory shaped as "
            r"{results_drive}\USB-IF Results\{product}\{firmware_version}"
        ),
    )
    return parser


def _run_parser(directory: str, parser: argparse.ArgumentParser) -> None:
    from .results_parser import ResultsParseError, write_results

    try:
        destination = write_results(directory)
    except ResultsParseError as exc:
        parser.error(str(exc))
    print(destination)


def main(argv: Sequence[str] | None = None) -> None:
    """Run automation or parse a firmware directory of existing reports."""
    command_arguments = list(sys.argv[1:] if argv is None else argv)
    parser = _parser()
    arguments = parser.parse_args(command_arguments)
    if arguments.command == "parse":
        _run_parser(arguments.directory, parser)
        return

    if arguments.command == "qual":
        runpy.run_module("cv_suite_automator.qualification", run_name="__main__")
        return

    original_argv = sys.argv
    sys.argv = [original_argv[0], arguments.chipset]
    try:
        runpy.run_module("cv_suite_automator.__main__", run_name="__main__")
    finally:
        sys.argv = original_argv
