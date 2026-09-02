import logging

from .logging_config import configure_logging

configure_logging()

from .core import *
from .report_collector import ReportCollector, ReportTransferError


logger = logging.getLogger(__name__)

"""
Main entry point of the CV Suite automation script.

- Validates that one argument is passed (bridge controller chipset).
- Creates a CVSuiteAutomation instance which automatically discovers
    and links multi-OS test sessions.
- Orchestrates the test flows for USB controllers (e.g., ASMedia / Intel)
    under both USB protocols (2 and 3).
- Copies or merges test result files from the default CV Suite directory
    to user-defined locations.
- Prompts the user at specific times to physically reconnect the device
    to different USB ports or controllers as needed.

Usage:
    python cv_suite_automation.py <bridge_controller_chipset>

Example:
    python cv_suite_automation.py 3861EN-FL
"""

# Check CLI arguments.
if len(sys.argv) != 2:
    logger.info("""
One argument is required for this program:
1 - (str) Bridge Controller Chipset
    """)
    sys.exit(1)

# Create an automation object. The __init__ method now handles all session logic.
cv_suite = CVSuiteAutomation()

# Load the summary data for the current session into the instance.
with open(cv_suite.destination_summary_json) as jsonFile:
    cv_suite.test_summary = json.load(jsonFile)

# Ensure the OS-specific reports directory exists for this run.
os.makedirs(cv_suite.destination_reports_dir, exist_ok=True)

# Attempt to run the test suite across both controllers (ASMedia and Intel).
controller_switched = False

# We loop twice—once for the current usb_controller_name, once after switching to the other.
for i in range(2):
    logger.info("- %s", cv_suite.usb_controller_name)

    # Start the CV Suite, select the current controller.
    time.sleep(10)
    cv_suite.start_cv_suite()
    
    # We manage USB 2 vs. USB 3 protocols in another loop.
    protocol_switched = False
    for _ in cv_suite.completed_test_list[cv_suite.usb_controller_name]:
        logger.info("-- USB%s", cv_suite.usb_protocol)
        report_collector = ReportCollector(cv_suite.source_reports_dir)

        # Decide which test to skip depending on the current USB protocol.
        if cv_suite.usb_protocol == 2:
            omit_test = 2
        else:
            omit_test = 1

        # Go through the tests in test_list and run them unless omitted.
        for key, value in cv_suite.test_list.items():
            if key == omit_test:
                continue

            cv_suite.current_test = key
            report_snapshot = report_collector.snapshot()
            try:
                cv_suite.run_test(test=key)
            finally:
                report_collector.capture_since(report_snapshot)

        # Move only reports produced by the automated tests in this protocol.
        report_destination = (
            f"{cv_suite.destination_reports_dir}\\{cv_suite.usb_controller_name}"
            f"\\USB{cv_suite.usb_protocol}"
        )
        report_fallback = (
            f"C:\\Users\\{cv_suite.windows_user_name}\\Desktop\\CV Reports"
        )
        report_relative_destination = Path(report_destination).relative_to(
            Path(cv_suite.destination_drive)
        )
        report_archive = (
            Path(cv_suite.source_reports_dir) / report_relative_destination
        )
        while True:
            try:
                report_collector.transfer(
                    report_destination,
                    report_archive,
                    report_fallback,
                )
                break
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

        # Switch from USB2 to USB3 or vice versa after the first set of tests.
        if not protocol_switched:
            if cv_suite.usb_protocol == 2:
                cv_suite.usb_protocol += 1  # Switch from USB2 -> USB3
            else:
                cv_suite.usb_protocol -= 1  # Switch from USB3 -> USB2
            controller.turn_off('usb3')               # Turn off USB3 (channel 14)
            time.sleep(15)
            protocol_switched = True

    # Close the CV Suite application.
    cv_suite.close_cv_suite()

    # Prompt the user to physically move the device to the other USB controller.
    controller.turn_on('usb3')

    # Switch from ASMedia -> Intel or Intel -> ASMedia for the second run.
    if not controller_switched:
        # Determine the new target controller
        if cv_suite.usb_controller_name == "ASMedia":
            new_controller_name = "Intel"
            new_controller_index = 1
        else:
            new_controller_name = "ASMedia"
            new_controller_index = 0
        
        # Power cycle the device port to ensure a clean re-detection
        # controller.turn_off('power')
        # time.sleep(1)
        # controller.turn_on('usb3')
        # controller.turn_on('power')

        logger.info("\n%s", "=" * 70)
        logger.info(
            "ACTION REQUIRED: Please move the device to a '%s' USB port.",
            new_controller_name,
        )
        logger.info("%s", "=" * 70)

        while True:
            # Use the bundled USB executable to see what's connected.
            device = find_apricorn_devices()
            
            if device:
                # A device was found. Check if it's on the correct controller.
                # Device discovery returns a list, so check the first element.
                detected_controller = device[0].usbController
                if detected_controller == new_controller_name:
                    print("")
                    break  # The device is on the new controller, exit the loop
                else:
                    # The device is connected, but still on the old controller.
                    time.sleep(5)
            else:
                # No device is detected at all.
                time.sleep(5)

        # Now that the device is in the right place, update the script's state
        cv_suite.usb_controller_name = new_controller_name
        cv_suite.usb_controller = new_controller_index
        cv_suite.usb_protocol = 3  # Reset to USB3 for the next controller
        controller_switched = True
        protocol_switched = False

# After all tests for the current OS are done, check if the whole session is complete.
# We do this by checking if the *other* OS's section in the summary file is still empty.
other_os_key = f'Windows {10 if cv_suite.windows_version == 11 else 11}'
is_session_now_complete = not cv_suite._is_os_section_empty(cv_suite.test_summary, other_os_key)

if not is_session_now_complete:
    logger.info("\n%s", "=" * 70)
    logger.info("OPERATING SYSTEM (Windows %s) TEST COMPLETE.", cv_suite.windows_version)
    logger.info("To finish the test session, please do the following:")
    logger.info("1. Reboot into the other operating system.")
    logger.info("2. Run the script again with the same command:")
    logger.info('   python cv_suite_automation.py "%s"', sys.argv[1])
    logger.info("The script will automatically find and continue this session.")
    logger.info("%s\n", "=" * 70)
else:
    logger.info("\n%s", "=" * 70)
    logger.info("BOTH OPERATING SYSTEMS HAVE BEEN TESTED.")
    logger.info("Test session '%s' is now complete.", cv_suite.test_datetime)
    logger.info("Final results are in: %s", cv_suite.destination_summary_json)
    logger.info("%s\n", "=" * 70)
