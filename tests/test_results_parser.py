# Literal counts keep the CV Suite failure examples readable.
# ruff: noqa: PLR0913, PLR2004

import json
import shutil
import uuid
from collections.abc import Iterator
from pathlib import Path

import pytest

from cv_suite_automator.results_parser import ResultsParseError, parse_results, write_results


@pytest.fixture
def scratch() -> Iterator[Path]:
    path = Path(".test-scratch") / f"parser-{uuid.uuid4().hex}"
    path.mkdir(parents=True)
    try:
        yield path
    finally:
        shutil.rmtree(path, ignore_errors=True)


def _firmware_directory(scratch: Path) -> Path:
    directory = scratch / "USB-IF Results" / "Product" / "v0001"
    directory.mkdir(parents=True)
    return directory


def _report(
    firmware: Path,
    capacity: str,
    *,
    session: str = "2026-09-04 1200",
    operating_system: str = "Windows 11",
    controller: str = "Intel",
    protocol: str = "USB2",
    suite: str = "Chapter 9 Tests [USB 2 devices]",
    result: str = "PASS [Fails (0); Aborts (0); Warnings (0)]",
    test_failures: tuple[tuple[str, int], ...] = (),
    filename: str = "report.html",
) -> Path:
    path = firmware / capacity / session / operating_system / controller / protocol / filename
    path.parent.mkdir(parents=True, exist_ok=True)
    failure_metadata = "\n".join(
        f"<META name='Test-Fail' content='{name} [Fails ({count}); Aborts (0); Warnings (0)]' />"
        for name, count in test_failures
    )
    path.write_text(
        "\n".join(
            (
                "<html><head>",
                f"<META name='Suite-Name' content='{suite}.cvtests' />",
                f"<META name='Suite-Result' content='{result}' />",
                failure_metadata,
                "</head></html>",
            )
        ),
        encoding="utf-8",
    )
    return path


def test_parses_all_attempts_sessions_and_aggregates_exact_failure_counts(scratch: Path) -> None:
    firmware = _firmware_directory(scratch)
    failing_test = "L1Suspend/Resume Test (Configuration Index 0)"
    _report(
        firmware,
        "4GB Phison",
        result="FAIL [Fails (2); Aborts (0); Warnings (0)]",
        test_failures=((failing_test, 2),),
        filename="failed.html",
    )
    _report(firmware, "4GB Phison", filename="passing-rerun.html")
    _report(
        firmware,
        "16GB Kioxia",
        session="2026-09-04 1300",
        result="FAIL [Fails (1); Aborts (0); Warnings (0)]",
        test_failures=((failing_test, 1),),
        filename="failed.html",
    )
    _report(firmware, "8GB Kioxia")

    result = parse_results(firmware)

    assert list(result) == ["aggregate", "capacities"]
    assert list(result["capacities"]) == ["4GB Phison", "8GB Kioxia", "16GB Kioxia"]
    assert result["capacities"]["8GB Kioxia"] == []
    assert result["capacities"]["4GB Phison"][0]["test"] == failing_test
    assert result["capacities"]["4GB Phison"][0]["occurrences"] == 2
    assert "DUTs" not in result["capacities"]["4GB Phison"][0]
    assert result["aggregate"][0]["occurrences"] == 3
    assert result["aggregate"][0]["DUTs"] == ["4GB Phison", "16GB Kioxia"]


def test_keeps_controller_protocol_and_suite_context_distinct(scratch: Path) -> None:
    firmware = _firmware_directory(scratch)
    for controller, protocol, suite in (
        ("ASMedia", "USB3", "Chapter 9 Tests [USB 3 Gen X devices]"),
        ("Intel", "USB2", "Chapter 9 Tests [USB 2 devices]"),
    ):
        _report(
            firmware,
            "32GB",
            controller=controller,
            protocol=protocol,
            suite=suite,
            result="FAIL [Fails (1); Aborts (0); Warnings (0)]",
            test_failures=(("Same test name", 1),),
            filename=f"{controller}.html",
        )

    result = parse_results(firmware)

    assert len(result["capacities"]["32GB"]) == 2
    assert len(result["aggregate"]) == 2
    assert all(failure["DUTs"] == ["32GB"] for failure in result["aggregate"])


def test_aggregate_duts_are_unique_across_attempts(scratch: Path) -> None:
    firmware = _firmware_directory(scratch)
    for session in ("2026-09-04 1200", "2026-09-04 1300"):
        _report(
            firmware,
            "512GB SMI",
            session=session,
            result="FAIL [Fails (2); Aborts (0); Warnings (0)]",
            test_failures=(("Repeated failure", 2),),
            filename=f"{session}.html",
        )

    result = parse_results(firmware)

    assert result["aggregate"][0]["occurrences"] == 4
    assert result["aggregate"][0]["DUTs"] == ["512GB SMI"]


def test_uses_suite_failure_when_no_test_failure_is_attributed(scratch: Path) -> None:
    firmware = _firmware_directory(scratch)
    _report(
        firmware,
        "64GB",
        result="FAIL [Fails (2); Aborts (2); Warnings (0)]",
    )

    result = parse_results(firmware)

    failure = result["capacities"]["64GB"][0]
    assert failure["test"] == "Unattributed suite failure"
    assert failure["occurrences"] == 2


def test_abort_only_report_does_not_create_a_failure(scratch: Path) -> None:
    firmware = _firmware_directory(scratch)
    _report(
        firmware,
        "128GB",
        result="FAIL [Fails (0); Aborts (1); Warnings (0)]",
    )

    assert parse_results(firmware) == {"aggregate": [], "capacities": {"128GB": []}}


def test_write_results_replaces_json_and_printable_payload_is_stable(scratch: Path) -> None:
    firmware = _firmware_directory(scratch)
    _report(firmware, "256GB")
    destination = firmware / "results.json"
    destination.write_text("old", encoding="utf-8")

    written = write_results(firmware)

    assert written == destination.resolve()
    assert json.loads(destination.read_text(encoding="utf-8")) == {
        "aggregate": [],
        "capacities": {"256GB": []},
    }
    assert destination.read_bytes().endswith(b"\n")


def test_rejects_product_directory(scratch: Path) -> None:
    firmware = _firmware_directory(scratch)
    _report(firmware, "4GB")

    with pytest.raises(ResultsParseError, match="Expected a firmware directory"):
        parse_results(firmware.parent)


@pytest.mark.parametrize("kind", ["missing", "file", "empty"])
def test_rejects_invalid_or_reportless_directory(scratch: Path, kind: str) -> None:
    if kind == "missing":
        directory = scratch / "USB-IF Results" / "Product" / "missing"
    else:
        directory = scratch / "USB-IF Results" / "Product" / kind
        directory.parent.mkdir(parents=True, exist_ok=True)
        if kind == "file":
            directory.write_text("not a directory", encoding="utf-8")
        else:
            directory.mkdir()

    with pytest.raises(ResultsParseError):
        parse_results(directory)
