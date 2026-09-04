"""Parse exact failures from a firmware directory of CV Suite reports."""

from __future__ import annotations

import json
import os
import re
import tempfile
from contextlib import suppress
from dataclasses import dataclass
from html.parser import HTMLParser
from pathlib import Path
from typing import Any


class ResultsParseError(ValueError):
    """Raised when a results directory or CV Suite report cannot be parsed safely."""


@dataclass(frozen=True)
class FailureIdentity:
    operating_system: str
    controller: str
    protocol: str
    suite: str
    test: str

    def as_json(
        self,
        occurrences: int | None = None,
        duts: list[str] | None = None,
    ) -> dict[str, str | int | list[str]]:
        result: dict[str, str | int | list[str]] = {
            "suite": self.suite,
            "test": self.test,
        }
        if occurrences is not None:
            result["occurrences"] = occurrences
        if duts is not None:
            result["DUTs"] = duts
        return result


class _MetadataParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.values: dict[str, list[str]] = {}
        self.has_ignored_failure = False

    def handle_starttag(
        self,
        tag: str,
        attrs: list[tuple[str, str | None]],
    ) -> None:
        if tag.casefold() != "meta":
            return
        attributes = {key.casefold(): value for key, value in attrs}
        name = attributes.get("name")
        content = attributes.get("content")
        if name is not None and content is not None:
            self.values.setdefault(name.casefold(), []).append(content)

    def handle_data(self, data: str) -> None:
        if data.strip().casefold() in _IGNORED_FAILURE_TEXTS:
            self.has_ignored_failure = True


_FAIL_COUNT = re.compile(r"\bFails\s*\(\s*(\d+)\s*\)", re.IGNORECASE)
_TEST_FAILURE = re.compile(
    r"^(?P<name>.*?)\s*\[\s*Fails\s*\(\s*(?P<count>\d+)\s*\)",
    re.IGNORECASE,
)
_NATURAL_PART = re.compile(r"(\d+)")
_IGNORED_FAILURE_TEXTS = frozenset(
    message.casefold()
    for message in (
        "No MSC/BOT Device selected for testing.",
        "No USB Device selected for testing.",
        (
            "This test suite is designed for Enhanced SuperSpeed devices only, but no "
            "Enhanced SuperSpeed devices have been detected."
        ),
    )
)


def _natural_key(value: str) -> tuple[tuple[int, int | str], ...]:
    return tuple(
        (0, int(part)) if part.isdigit() else (1, part.casefold())
        for part in _NATURAL_PART.split(value)
        if part
    )


def _failure_key(identity: FailureIdentity) -> tuple[str, ...]:
    return (
        identity.operating_system.casefold(),
        identity.controller.casefold(),
        identity.protocol.casefold(),
        identity.suite.casefold(),
        identity.test.casefold(),
    )


FailureJson = dict[str, str | int | list[str]]
GroupedFailures = dict[str, dict[str, dict[str, list[FailureJson]]]]


def _group_failures(
    totals: dict[FailureIdentity, int],
    *,
    include_occurrences: bool,
    duts: dict[FailureIdentity, set[str]] | None = None,
) -> GroupedFailures:
    grouped: GroupedFailures = {}
    for identity in sorted(totals, key=_failure_key):
        protocol_failures = (
            grouped.setdefault(identity.operating_system, {})
            .setdefault(identity.controller, {})
            .setdefault(identity.protocol, [])
        )
        identity_duts = None
        if duts is not None:
            identity_duts = sorted(duts[identity], key=_natural_key)
        occurrences = totals[identity] if include_occurrences else None
        protocol_failures.append(identity.as_json(occurrences, identity_duts))
    return grouped


def _read_report(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8-sig")
    except UnicodeDecodeError:
        try:
            return path.read_text(encoding="cp1252")
        except OSError as exc:
            raise ResultsParseError(f"Could not read report {path}: {exc}") from exc
    except OSError as exc:
        raise ResultsParseError(f"Could not read report {path}: {exc}") from exc


def _metadata(path: Path) -> _MetadataParser:
    parser = _MetadataParser()
    try:
        parser.feed(_read_report(path))
    except Exception as exc:
        if isinstance(exc, ResultsParseError):
            raise
        raise ResultsParseError(f"Could not parse report {path}: {exc}") from exc
    return parser


def _suite_name(metadata: dict[str, list[str]], path: Path) -> str:
    names = metadata.get("suite-name", [])
    if not names or not names[0].strip():
        raise ResultsParseError(f"Failed report has no Suite-Name metadata: {path}")
    name = names[0].strip()
    return name[:-8] if name.casefold().endswith(".cvtests") else name


def _reported_count(value: str, path: Path, label: str) -> int:
    match = _FAIL_COUNT.search(value)
    if match is None:
        raise ResultsParseError(f"Malformed {label} failure count in report: {path}")
    return int(match.group(1))


def _report_failures(
    path: Path,
    context: tuple[str, str, str],
) -> list[tuple[FailureIdentity, int]] | None:
    parsed_report = _metadata(path)
    metadata = parsed_report.values
    suite_results = metadata.get("suite-result", [])
    if not suite_results:
        return None
    suite_result = suite_results[0].strip()
    if not suite_result.casefold().startswith("fail"):
        return []

    operating_system, controller, protocol = context
    suite = _suite_name(metadata, path)
    failures: list[tuple[FailureIdentity, int]] = []
    for value in metadata.get("test-fail", []):
        match = _TEST_FAILURE.search(value.strip())
        if match is None:
            raise ResultsParseError(f"Malformed Test-Fail metadata in report: {path}")
        count = int(match.group("count"))
        if count > 0:
            failures.append(
                (
                    FailureIdentity(
                        operating_system,
                        controller,
                        protocol,
                        suite,
                        match.group("name").strip(),
                    ),
                    count,
                )
            )

    suite_count = _reported_count(suite_result, path, "suite")
    if not failures and suite_count > 0 and not parsed_report.has_ignored_failure:
        failures.append(
            (
                FailureIdentity(
                    operating_system,
                    controller,
                    protocol,
                    suite,
                    "Unattributed suite failure",
                ),
                suite_count,
            )
        )
    return failures


def _firmware_directory(directory: str | Path) -> Path:
    path = Path(directory).expanduser().resolve()
    if not path.exists():
        raise ResultsParseError(f"Results directory does not exist: {path}")
    if not path.is_dir():
        raise ResultsParseError(f"Results path is not a directory: {path}")
    if path.parent.parent.name.casefold() != "usb-if results":
        raise ResultsParseError(
            "Expected a firmware directory shaped as "
            r"{results_drive}\USB-IF Results\{product}\{firmware_version}: "
            f"{path}"
        )
    return path


def _report_paths(directory: Path) -> list[Path]:
    return sorted(
        directory.glob("*/*/*/*/*/*.html"),
        key=lambda path: tuple(part.casefold() for part in path.relative_to(directory).parts),
    )


def parse_results(directory: str | Path) -> dict[str, Any]:
    """Return per-capacity and aggregate exact failures for one firmware directory."""
    firmware_directory = _firmware_directory(directory)
    report_paths = _report_paths(firmware_directory)
    if not report_paths:
        raise ResultsParseError(f"No CV Suite HTML reports found in: {firmware_directory}")

    capacity_failures: dict[str, dict[FailureIdentity, int]] = {}
    aggregate: dict[FailureIdentity, int] = {}
    aggregate_duts: dict[FailureIdentity, set[str]] = {}
    recognized_reports = 0
    for report_path in report_paths:
        relative = report_path.relative_to(firmware_directory)
        capacity, _session, operating_system, controller, protocol, _filename = relative.parts
        failures = _report_failures(
            report_path,
            (operating_system, controller, protocol),
        )
        if failures is None:
            continue
        recognized_reports += 1
        capacity_totals = capacity_failures.setdefault(capacity, {})
        for identity, count in failures:
            capacity_totals[identity] = capacity_totals.get(identity, 0) + count
            aggregate[identity] = aggregate.get(identity, 0) + count
            aggregate_duts.setdefault(identity, set()).add(capacity)

    if recognized_reports == 0:
        raise ResultsParseError(f"No recognizable CV Suite reports found in: {firmware_directory}")

    capacities = {
        capacity: _group_failures(totals, include_occurrences=False)
        for capacity, totals in sorted(
            capacity_failures.items(),
            key=lambda item: _natural_key(item[0]),
        )
    }
    aggregate_json = _group_failures(
        aggregate,
        include_occurrences=True,
        duts=aggregate_duts,
    )
    return {"aggregate": aggregate_json, "capacities": capacities}


def write_results(directory: str | Path) -> Path:
    """Parse a firmware directory and atomically replace its results.json."""
    firmware_directory = _firmware_directory(directory)
    result = parse_results(firmware_directory)
    destination = firmware_directory / "results.json"
    temporary_name: str | None = None
    try:
        with tempfile.NamedTemporaryFile(
            "w",
            encoding="utf-8",
            newline="\n",
            dir=firmware_directory,
            prefix=".results-",
            suffix=".json.tmp",
            delete=False,
        ) as stream:
            temporary_name = stream.name
            json.dump(result, stream, indent=2, ensure_ascii=False)
            stream.write("\n")
        os.replace(temporary_name, destination)
    except OSError as exc:
        raise ResultsParseError(f"Could not write {destination}: {exc}") from exc
    finally:
        if temporary_name is not None:
            with suppress(OSError):
                Path(temporary_name).unlink(missing_ok=True)
    return destination
