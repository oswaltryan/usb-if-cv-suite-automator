"""Three-attempt MSC storage qualification workflow."""

from __future__ import annotations

import json
import logging
import os
import time
import uuid
from collections.abc import Callable, Iterable
from pathlib import Path
from typing import Any, Protocol

from .logging_config import configure_logging
from .report_collector import ReportCollector, ReportTransferError
from .ui_supervisor import TestOutcome

MSC_TEST_ID = 17
ATTEMPT_COUNT = 3
USB3_PROTOCOL = 3

logger = logging.getLogger(__name__)


class QualificationAutomation(Protocol):
    """Automation surface needed by the qualification runner."""

    destination_drive: str
    destination_reports_dir: str
    destination_summary_json: str
    source_reports_dir: str
    usb_controller_name: str
    usb_protocol: int
    windows_version: int
    current_test: int | None
    user_home: Path
    ui_supervisor: Any
    device: Any
    usb_controller: int

    def start_cv_suite(self) -> None: ...

    def run_test(self, test: int, *, record_outcome: bool = True) -> TestOutcome: ...

    def close_cv_suite(self) -> None: ...


def wait_for_usb3_device(
    automation: QualificationAutomation,
    device_finder: Callable[[], Iterable[Any]],
    sleeper: Callable[[float], None] = time.sleep,
    poll_interval: float = 5,
) -> None:
    """Wait until the current DUT is reconnected over USB3."""
    if automation.usb_protocol == USB3_PROTOCOL:
        return

    expected_vendor = automation.device.idVendor.casefold()
    expected_product = automation.device.idProduct.casefold()
    logger.info("%s", "=" * 70)
    logger.info("ACTION REQUIRED: The DUT is currently connected as USB2.")
    logger.info(
        "Connect and unlock this DUT on a USB3 port. Qualification will resume automatically."
    )
    logger.info("%s", "=" * 70)

    while True:
        matching_device = next(
            (
                device
                for device in device_finder()
                if device.idVendor.casefold() == expected_vendor
                and device.idProduct.casefold() == expected_product
                and int(device.bcdUSB) == USB3_PROTOCOL
            ),
            None,
        )
        if matching_device is not None:
            automation.device = matching_device
            automation.usb_protocol = USB3_PROTOCOL
            automation.usb_controller_name = matching_device.usbController
            automation.usb_controller = 0 if matching_device.usbController == "ASMedia" else 1
            logger.info(
                "DUT detected on USB3 using the %s controller. Continuing qualification.",
                automation.usb_controller_name,
            )
            return
        sleeper(poll_interval)


def new_qualification_summary(automation: QualificationAutomation) -> dict[str, Any]:
    """Create the initial, durable summary for a qualification session."""
    return {
        "test": "MSC Tests",
        "operating_system": f"Windows {automation.windows_version}",
        "controller": automation.usb_controller_name,
        "protocol": f"USB{automation.usb_protocol}",
        "attempts": [],
        "overall_status": "In Progress",
    }


def add_attempt(
    summary: dict[str, Any],
    attempt_number: int,
    outcome: TestOutcome,
) -> None:
    """Append one completed attempt and finalize after the third one."""
    summary["attempts"].append(
        {
            "attempt": attempt_number,
            "tests_run": outcome.tests_run,
            "failures": outcome.failures,
            "status": outcome.status,
            "reason": outcome.reason,
        }
    )
    if len(summary["attempts"]) == ATTEMPT_COUNT:
        summary["overall_status"] = (
            "Pass"
            if all(attempt["status"] == "Pass" for attempt in summary["attempts"])
            else "Fail"
        )


def write_qualification_summary(summary: dict[str, Any], destination: str | Path) -> None:
    """Atomically replace the qualification summary on disk."""
    destination_path = Path(destination)
    destination_path.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination_path.with_name(f".{destination_path.name}.{uuid.uuid4().hex}.tmp")
    try:
        with temporary.open("w", encoding="utf-8", newline="\n") as stream:
            json.dump(summary, stream, indent=2, ensure_ascii=False)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, destination_path)
    finally:
        temporary.unlink(missing_ok=True)


def _transfer_reports(
    automation: QualificationAutomation,
    collector: ReportCollector,
) -> None:
    report_destination = (
        f"{automation.destination_reports_dir}\\{automation.usb_controller_name}"
        f"\\USB{automation.usb_protocol}"
    )
    report_fallback = automation.user_home / "Desktop" / "CV Reports"
    relative_destination = Path(report_destination).relative_to(Path(automation.destination_drive))
    report_archive = Path(automation.source_reports_dir) / relative_destination
    while True:
        try:
            collector.transfer(report_destination, report_archive, report_fallback)
            return
        except ReportTransferError as exc:
            automation.ui_supervisor.operator_checkpoint(
                "Could not safely back up CV Suite reports: "
                f"{exc}. Correct the storage condition, then press ENTER."
            )


def _run_attempts(
    automation: QualificationAutomation,
    report_collector: ReportCollector,
    summary: dict[str, Any],
) -> None:
    """Execute and persist the three MSC qualification attempts."""
    for attempt_number in range(1, ATTEMPT_COUNT + 1):
        logger.info("MSC qualification attempt %s of %s", attempt_number, ATTEMPT_COUNT)
        automation.current_test = MSC_TEST_ID
        report_snapshot = report_collector.snapshot()
        try:
            outcome = automation.run_test(test=MSC_TEST_ID, record_outcome=False)
        finally:
            report_collector.capture_since(report_snapshot)
        add_attempt(summary, attempt_number, outcome)
        write_qualification_summary(summary, automation.destination_summary_json)
        logger.info("--- Attempt %s: %s", attempt_number, outcome.summary_values())
        if outcome.reason:
            logger.info("    %s", outcome.reason)


def run_qualification(
    automation: QualificationAutomation,
    collector: ReportCollector | None = None,
    device_finder: Callable[[], Iterable[Any]] | None = None,
    sleeper: Callable[[float], None] = time.sleep,
) -> int:
    """Run MSC Tests three times and persist every completed attempt."""
    if device_finder is None:
        from .usb_executable import find_apricorn_devices

        device_finder = find_apricorn_devices
    wait_for_usb3_device(automation, device_finder, sleeper)

    summary = new_qualification_summary(automation)
    write_qualification_summary(summary, automation.destination_summary_json)
    report_collector = collector or ReportCollector(automation.source_reports_dir)

    try:
        automation.start_cv_suite()
        _run_attempts(automation, report_collector, summary)
        _transfer_reports(automation, report_collector)
    finally:
        automation.close_cv_suite()

    logger.info("%s", "=" * 70)
    logger.info("STORAGE QUALIFICATION COMPLETE")
    logger.info("Overall status: %s", summary["overall_status"])
    logger.info("Results: %s", automation.destination_summary_json)
    logger.info("%s", "=" * 70)
    return 0


def main() -> int:
    """Initialize hardware-backed automation and run qualification."""
    configure_logging()
    from .core import CVSuiteAutomation

    automation = CVSuiteAutomation(None, qualification=True)
    return run_qualification(automation)


if __name__ == "__main__":
    raise SystemExit(main())
