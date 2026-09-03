"""Interactive entry point for CV Suite automation."""

import json
import logging
import os
import sys
import time
from pathlib import Path

from .logging_config import configure_logging


configure_logging()
logger = logging.getLogger(__name__)

if len(sys.argv) != 2:
    logger.info(
        "\nOne argument is required for this program:\n"
        "1 - (str) Bridge Controller Chipset"
    )
    sys.exit(1)

from .report_collector import ReportCollector, ReportTransferError
from .run_config import (
    ordered_controllers,
    ordered_protocols,
    prompt_run_selection,
    resolve_device_capabilities,
)


# Collect all user choices before importing core, which initializes the
# switchboard and begins DUT enumeration as an import-time side effect.
run_selection = prompt_run_selection(supports_uasp=None)

from .core import CVSuiteAutomation, controller
from .usb_executable import find_apricorn_devices


cv_suite = CVSuiteAutomation()
run_selection = resolve_device_capabilities(
    run_selection, cv_suite.device.uses_uasp
)
with open(cv_suite.destination_summary_json) as json_file:
    cv_suite.test_summary = json.load(json_file)
os.makedirs(cv_suite.destination_reports_dir, exist_ok=True)


def move_to_controller(target_controller: str) -> None:
    """Wait until the exact DUT is attached to the requested controller."""
    if cv_suite.usb_controller_name == target_controller:
        return
    controller.turn_on("usb3")
    print()
    logger.info("%s", "=" * 70)
    logger.info(
        "ACTION REQUIRED: Please move the device to a '%s' USB port.",
        target_controller,
    )
    logger.info("%s", "=" * 70)
    while True:
        matching_device = next(
            (
                device
                for device in find_apricorn_devices()
                if device.idVendor.casefold() == cv_suite.device.idVendor.casefold()
                and device.idProduct.casefold() == cv_suite.device.idProduct.casefold()
                and device.usbController == target_controller
            ),
            None,
        )
        if matching_device is not None:
            cv_suite.device = matching_device
            cv_suite.usb_controller_name = target_controller
            cv_suite.usb_controller = 0 if target_controller == "ASMedia" else 1
            cv_suite.usb_protocol = 3
            return
        time.sleep(5)


def select_protocol(protocol: int) -> None:
    """Put the switchboard in the requested USB mode when it changes."""
    if cv_suite.usb_protocol == protocol:
        return
    if protocol == 3:
        controller.turn_on("usb3")
    else:
        controller.turn_off("usb3")
    cv_suite.usb_protocol = protocol
    time.sleep(15)


def collect_reports(collector: ReportCollector) -> None:
    report_destination = (
        f"{cv_suite.destination_reports_dir}\\{cv_suite.usb_controller_name}"
        f"\\USB{cv_suite.usb_protocol}"
    )
    report_fallback = str(cv_suite.user_home / "Desktop" / "CV Reports")
    relative_destination = Path(report_destination).relative_to(
        Path(cv_suite.destination_drive)
    )
    report_archive = Path(cv_suite.source_reports_dir) / relative_destination
    while True:
        try:
            collector.transfer(report_destination, report_archive, report_fallback)
            return
        except ReportTransferError as exc:
            cv_suite.ui_supervisor.operator_checkpoint(
                "Could not safely back up CV Suite reports: "
                f"{exc}. Correct the storage condition, then press ENTER.",
                context={
                    "phase": "report transfer",
                    "controller": cv_suite.usb_controller_name,
                    "protocol": cv_suite.usb_protocol,
                },
            )


controllers_to_run = ordered_controllers(
    run_selection.controllers, cv_suite.usb_controller_name
)
protocols_to_run = ordered_protocols(run_selection.protocols)

for target_controller in controllers_to_run:
    move_to_controller(target_controller)
    logger.info("- %s", cv_suite.usb_controller_name)
    select_protocol(protocols_to_run[0])
    time.sleep(10)
    cv_suite.start_cv_suite()

    for protocol in protocols_to_run:
        select_protocol(protocol)
        logger.info("-- USB%s", protocol)
        report_collector = ReportCollector(cv_suite.source_reports_dir)
        for test_id in run_selection.test_ids(protocol):
            cv_suite.current_test = test_id
            report_snapshot = report_collector.snapshot()
            try:
                cv_suite.run_test(test=test_id)
            finally:
                report_collector.capture_since(report_snapshot)
        collect_reports(report_collector)

    cv_suite.close_cv_suite()


test_labels = {
    "chapter9": "Chapter 9 Tests",
    "connector": "Connector Type Tests",
    "summary": "Device Summary",
    "msc": "MSC Tests",
    "uasp": "UASP Tests",
}
print()
logger.info("%s", "=" * 70)
logger.info("SELECTED RUN COMPLETE (Windows %s)", cv_suite.windows_version)
logger.info(
    "Tests: %s", ", ".join(test_labels[test] for test in run_selection.tests)
)
logger.info("Controllers: %s", ", ".join(run_selection.controllers))
logger.info(
    "Protocols: %s",
    ", ".join(f"USB{protocol}" for protocol in run_selection.protocols),
)
logger.info("Results: %s", cv_suite.destination_summary_json)
logger.info("%s\n", "=" * 70)
