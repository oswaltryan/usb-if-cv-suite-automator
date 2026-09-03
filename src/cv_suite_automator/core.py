"""
CV Suite Automation Script

This script automates USB testing using the CV Suite application. It allows
users to select tests, handle dialog boxes, and manage the execution flow
for USB devices.

Classes:
    CVSuiteAutomation:
        A class that encapsulates the logic for launching the CV Suite
        application, selecting USB controllers, executing tests, and
        handling test dialogs.

Report files are collected by the entry point after each automated test and
transferred only when they can be attributed to the current run.

Usage:
    Run the script with the following argument:
        1) A string specifying the Bridge Controller Chipset, e.g.
           3861EN-FL or 3639EN-FL.

Example:
    python cv_suite_automation.py 3861EN-FL
"""

import datetime
import json
import logging
import os
import io
import re
import sys
import time
import shutil
import platform
from pathlib import Path

from contextlib import redirect_stdout
from pprint import pprint
from pywinauto import Application
from pywinauto.keyboard import send_keys

# These are local imports in your environment:
from .hardware import IOController
from .logging_config import timestamped_prompt
from .ui_supervisor import (
    CVSuiteUISupervisor,
    DialogRule,
    LOG_CONTROL_ID,
    TestOutcome,
)
from .usb_executable import find_apricorn_devices
from .utils import *


logger = logging.getLogger(__name__)

controller = IOController()              # Initialize controller
controller.turn_on('power')               # Turn on power (channel 13)
controller.turn_on('usb3')                # Turn on USB3 (channel 14)

logger.info("Searching for a connected and unlocked Apricorn device...")
logger.info("Please plug the device into the USB2/3 switchboard and unlock it.")

device_handle = None
while not device_handle:
    # Attempt to find the device
    device_handle = find_apricorn_devices()
    
    if not device_handle:
        time.sleep(15)
        # If no device is found, wait a few seconds and try again.
    else:
        break

# A short pause to ensure the device is fully initialized by the OS
time.sleep(2)

class CVSuiteAutomation:
    """
    A class to automate testing processes in the CV Suite application.

    Attributes:
        test_description_input (str):
            A user- or CLI-provided string describing the test. Combined with
            the device name (self.device.iProduct) and used in the UI.

        usb_controller (int):
            The numeric index passed to CV Suite's ListBox for selecting
            the USB controller. Derived from 'usb_controller_name'.

        usb_controller_name (str):
            The name of the USB controller. Typically 'ASMedia' or 'Intel',
            depending on the discovered device.

        usb_protocol (int):
            USB protocol version (2 or 3). Derived from the device bcdUSB.

        windows_version (int):
            The detected Windows major version (10 or 11). Used for file paths.

        windows_user_name (str):
            The local username corresponding to the Windows version.
            E.g., "Testing" on Win10 or "itadmin" on Win11.

        test_datetime (str):
            A timestamp (YYYY-MM-DD HHMM) captured at initialization to
            differentiate test runs.

        source_reports_dir (str):
            Path to the generated CV Suite reports folder.

        source_summary_json (str):
            File path to the template summary JSON (pre-filled, e.g. blank arrays).

        destination_drive (str):
            The drive letter for saving final test output (e.g., 'Z:').

        destination_reports_dir (str):
            Directory under 'destination_drive' where test results are copied.

        destination_summary_json (str):
            Full path to the summary.json where test outcomes are consolidated.

        app (Application):
            A pywinauto Application instance for controlling CV Suite.

        main_window (WindowSpecification):
            A handle to the main CV Suite window.

        log_window (WindowSpecification):
            A handle to the text log area in CV Suite.

        current_test (int or None):
            The ID of the currently executing test from self.test_list.

        test_list (dict):
            A dictionary describing which tests are available, with
            details like 'dialog_strings' for prompting the user.

        completed_test_list (dict):
            Tracks completed tests by controller name and protocol.
            For example, self.completed_test_list["ASMedia"][2] might
            list tests run on an ASMedia controller under USB2.

        test_summary (dict):
            A dynamic structure representing test outcomes. Contents
            are written to summary.json after each test.

        failure_messages (list):
            A list of strings signifying certain known failure states.

    Methods:
        __init__():
            Sets up all initial data, like the device under test and
            file paths for storing results. Reads one CLI argument.

        start_cv_suite():
            Launches the CV Suite application, selects the USB controller,
            and confirms the selection via a popup dialog.

        run_test(test: int):
            Starts and supervises a test, handles its dialogs in any order,
            and records its result.

        close_cv_suite():
            Closes the CV Suite main window.

    Example:
        cv_suite = CVSuiteAutomation()
        cv_suite.start_cv_suite()
        cv_suite.run_test(6)
        cv_suite.close_cv_suite()
    """

    def __init__(self):
        """
        Initializes the CVSuiteAutomation class by detecting the device,
        OS, and automatically finding or creating a test session.
        """
        # --- Stage 1: Basic device and environment detection ---
        # Attempt to locate a recognized Apricorn device (custom function).
        self.device = find_apricorn_devices()
        if not self.device:
            logger.error("No device found.")
            sys.exit(1)  # Exit if no device is found.
        elif len(self.device) > 2:
            logger.error("Too many Apricorn devices connected")
            sys.exit(1)  # Exit if no device is found.
        else:
            for dut in range(len(self.device)):
                if self.device[dut].idProduct == '0351':
                    self.device.pop(dut)
                    break
            if len(self.device) > 1:
                logger.error("Too many Apricorn devices connected")
                sys.exit(1)  # Exit if no device is found.

        self.device = self.device[0]

        # Use the device’s USB controller name to determine the integer index for CV Suite’s UI.
        self.usb_controller_name = self.device.usbController
        if self.usb_controller_name == "ASMedia":
            self.usb_controller = 0
        else:
            self.usb_controller = 1

        # Detect Windows version (10 or 11) and set user name accordingly.
        self.windows_version = int(platform.win32_ver()[0])
        if self.windows_version == 10:
            self.windows_user_name = "Testing"
        elif self.windows_version == 11:
            self.windows_user_name = "itadmin"

        # sys.argv[1] is expected to be the "bridge controller chipset" string.
        # We also append the device model name (self.device.iProduct).
        self.test_description_input = sys.argv[1] + " " + self.device.iProduct

        # bcdUSB might look like "3.2" => self.usb_protocol = 3
        self.usb_protocol = int(self.device.bcdUSB)

        # Define base paths needed for the session discovery logic
        self.destination_drive = 'M:\\USB-IF Results'
        self.source_summary_json = (
            f'C:\\Users\\{self.windows_user_name}\\Desktop\\cv_suite_testing\\src\\cv_suite_automator\\summary_template.json'
        )

        # --- Stage 2: Find or create the test session using our new helper method ---
        self.test_datetime = self._find_or_create_session()

        # --- Stage 3: Define all paths based on the discovered or created session ID ---
        self.session_dir = (
            f'{self.destination_drive}\\{self.test_description_input}\\'
            f'v{self.device.bcdDevice}\\{self.device.driveSizeGB}GB\\'
            f'{self.test_datetime}'
        )
        self.destination_reports_dir = f'{self.session_dir}\\Windows {self.windows_version}'
        self.destination_summary_json = f'{self.session_dir}\\summary.json'
        
        self.source_reports_dir = (
            f'C:\\Users\\{self.windows_user_name}\\Documents\\USB-IF Test Suite\\CV Reports\\USB3CV'
        )

        # --- Stage 4: Initialize application and test state variables (unchanged from original) ---
        # Initialize pywinauto objects
        self.app = None
        self.main_window = None
        self.log_window = None
        self.ui_supervisor = None
        self.current_test = None

        # List of tests we might execute.
        self.test_list = {
            1: {
                "test_number": 1,
                "name": "Chapter 9 Tests [USB 2 devices]",
                "dialog_strings": {
                    1: "Please run Connector Type Tests on this device.",
                    2: "Please run MSC/BOT Tests on this device."
                }
            },
            2: {
                "test_number": 2,
                "name": "Chapter 9 Tests [USB 3 Gen X devices]",
                "dialog_strings": {
                    1: "Please run Chapter 9 Tests on this device as a USB 2.0 device at all supported USB 2.0 speeds.",
                    2: "Please run Connector Type Tests on this device.",
                    3: "Please run MSC/BOT Tests on this device."
                }
            },
            3: {
                "test_number": 3,
                "name": "Connector Type Tests",
                "dialog_strings": {
                    1: "Select power connection for DUT",
                    2: "Is Device Under Test an Embedded Device?"
                }
            },
            6: {
                "test_number": 6,
                "name": "Device Summary",
                "dialog_strings": {}
            }
        }

        # Keep track of which tests each controller has completed for each protocol.
        self.completed_test_list = {
            "ASMedia": {2: [], 3: []},
            "Intel": {2: [], 3: []}
        }

        # Summaries will store pass/fail data. Appended at runtime.
        self.test_summary = {}

        # Known error messages we might see in the UI log for certain failing conditions:
        self.failure_messages = [
            "This test suite is designed for Enhanced SuperSpeed devices only, but no Enhanced SuperSpeed devices have been detected.",
            "A Device Under Test was not set.",
            "No Device Under Test"
        ]

        # Check if device is UASP and update test list accordingly
        if self.device.uses_uasp:
            self.test_list[1].update({
                "dialog_strings": {
                    1: "Please run Connector Type Tests on this device.",
                    2: "Please run MSC/BOT Tests on this device.",
                    3: "Please run MSC/UASP Tests on this device."}
            })
            self.test_list[2].update({
                "dialog_strings": {
                    1: "Please run Chapter 9 Tests on this device as a USB 2.0 device at all supported USB 2.0 speeds.",
                    2: "Please run Connector Type Tests on this device.",
                    3: "Please run MSC/BOT Tests on this device.",
                    4: "Please run MSC/UASP Tests on this device."
            }})
            self.test_list.update({21: {
                "test_number": 21,
                "name": "UASP Tests",
                "dialog_strings": {
                    1: "WARNING: The following test might destroy ALL data on this disk.  To continue with all tests, click OK.  To abort this test, click ABORT",
                    2: "1) Please unplug and power off the device.",
                    3: "Is the device capable of detecting power loss states?"
                }
            }})
            self.test_list.update({17: {
                "test_number": 17,
                "name": "MSC Tests",
                "dialog_strings": {
                    1: "WARNING: The following test might destroy ALL data on this disk.  To continue with all tests, click OK.  To abort this test, click ABORT",
                    2: "Disconnect and power off MSC device, then click OK.  To abort this test, click ABORT"
                }
            }})
        else:
            self.test_list.update({17: {
                "test_number": 17,
                "name": "MSC Tests",
                "dialog_strings": {
                    1: "WARNING: The following test might destroy ALL data on this disk.  To continue with all tests, click OK.  To abort this test, click ABORT",
                    2: "Disconnect and power off MSC device, then click OK.  To abort this test, click ABORT"
                }
            }})

    def _is_os_section_empty(self, summary_data: dict, os_key: str) -> bool:
        """Checks if a given OS section in the summary data is empty."""
        try:
            os_data = summary_data[os_key]
            for controller in os_data.values():
                for protocol in controller.values():
                    for test_results in protocol.values():
                        if test_results:  # An empty list is False, a non-empty list is True
                            return False
        except KeyError:
            # If the OS key doesn't even exist, it's definitely "empty"
            return True
        return True

    def _find_or_create_session(self):
        """
        Finds a session to latch onto or creates a new one based on strict rules.

        - Latching is ONLY allowed if the most recent session was started on the
          *other* OS, is incomplete, and was created within a short time window.
        - In ALL other cases, a new session is created.
        - No data is ever overwritten or deleted.

        Returns:
            str: The session timestamp (e.g., "2023-10-27 1430").
        """
        # --- Latching is only allowed for sessions newer than this (in minutes) ---
        # This window should be just long enough to allow for the automated
        # OS reboot and script startup process.
        LATCH_WINDOW_MINUTES = 120  # 2 hours

        base_device_dir = (
            f'{self.destination_drive}\\{self.test_description_input}\\'
            f'v{self.device.bcdDevice}\\{self.device.driveSizeGB}GB'
        )
        os.makedirs(base_device_dir, exist_ok=True)

        try:
            # Get existing session folders, sorted with the newest one first.
            session_folders = sorted(
                [d for d in os.listdir(base_device_dir) if os.path.isdir(os.path.join(base_device_dir, d))],
                reverse=True
            )
        except FileNotFoundError:
            session_folders = []

        # Only check the single most recent session folder for a potential latch.
        if session_folders:
            latest_session_id = session_folders[0]
            
            # 1. Check if the session is a valid timestamp
            try:
                session_time = datetime.datetime.strptime(latest_session_id, "%Y-%m-%d %H%M")
                time_since_session = datetime.datetime.now() - session_time
            except ValueError:
                # If the folder name isn't a timestamp, it can't be latched.
                latest_session_id = None

            if latest_session_id:
                # 2. Check if the session is within the allowed time window
                if time_since_session.total_seconds() < (LATCH_WINDOW_MINUTES * 60):
                    summary_path = os.path.join(base_device_dir, latest_session_id, 'summary.json')
                    
                    if os.path.exists(summary_path):
                        try:
                            with open(summary_path, 'r') as f:
                                summary_data = json.load(f)

                            current_os_key = f'Windows {self.windows_version}'
                            other_os_key = f'Windows {10 if self.windows_version == 11 else 11}'

                            is_current_empty = self._is_os_section_empty(summary_data, current_os_key)
                            is_other_empty = self._is_os_section_empty(summary_data, other_os_key)

                            # 3. Check if the session state is correct for latching
                            # (Current OS section must be empty, other OS must not be)
                            if is_current_empty and not is_other_empty:
                                logger.info(
                                    "Found recent session '%s' from other OS. Latching onto it.",
                                    latest_session_id,
                                )
                                return latest_session_id

                        except (json.JSONDecodeError, IOError):
                            logger.warning(
                                "Warning: Could not read or parse summary for session '%s'.",
                                latest_session_id,
                            )

        # If we reach this point, no valid session was found to latch onto.
        # Create a new session.
        logger.info("No suitable recent session to latch onto. Creating a new test session.")
        print("")
        new_session_id = time.strftime("%Y-%m-%d %H%M", time.localtime())
        new_session_path = os.path.join(base_device_dir, new_session_id)
        os.makedirs(new_session_path, exist_ok=True)
        destination_summary_json = os.path.join(new_session_path, 'summary.json')
        shutil.copy(src=self.source_summary_json, dst=destination_summary_json)
        
        return new_session_id


    def start_cv_suite(self):
        """
        Launches the CV Suite application and confirms the chosen USB controller.

        - Locates and opens the shortcut for CV Suite (named "USB3CV - USB 3 Gen X.lnk").
        - Waits a moment for the app to load.
        - Connects via pywinauto to the main window titled "USB 3 Gen X Command Verifier".
        - Selects the USB controller (0-based index) from a ListBox.
        - Confirms the prompt "Do you want to continue with the host controller you have selected?".
        """
        # Launch the application using its .lnk desktop shortcut.
        shortcut = f"C:\\Users\\{self.windows_user_name}\\Desktop\\USB3CV - USB 3 Gen X.lnk"
        os.startfile(shortcut)
        # Preserve the foreground handoff that CV Suite needs during startup.
        time.sleep(1)

        attempts = 0
        deadline = time.monotonic() + 60
        last_error = "CV Suite did not become available"
        while True:
            try:
                self.app = Application().connect(
                    title=r"USB 3 Gen X Command Verifier", timeout=5
                )
                self.main_window = self.app.window(
                    best_match=r"USB 3 Gen X Command Verifier"
                )
                self.log_window = self.main_window.child_window(
                    control_id=LOG_CONTROL_ID
                )
                if self.main_window.exists(timeout=2):
                    break
            except Exception as exc:
                attempts += 1
                last_error = exc

            if attempts >= 3 or time.monotonic() >= deadline:
                print()
                logger.info("%s", "=" * 70)
                logger.info("OPERATOR ACTION REQUIRED")
                logger.error("Could not connect to CV Suite: %s", last_error)
                logger.info("Start or restore CV Suite, then return to this window.")
                logger.info("%s", "=" * 70)
                input(timestamped_prompt("Press ENTER to retry: "))
                attempts = 0
                deadline = time.monotonic() + 60
            time.sleep(1)

        self.ui_supervisor = CVSuiteUISupervisor(
            self.app,
            self.main_window,
            self.log_window,
            Path(self.session_dir) / "diagnostics",
            self.failure_messages,
        )
        self.ui_supervisor.focus_main_window()

        def select_controller():
            list_box = self.main_window.child_window(best_match="ListBox")
            list_box.wait("exists enabled visible ready", timeout=20)
            list_box.select(self.usb_controller)
            continue_button = self.main_window.child_window(best_match="Continue")
            continue_button.wait("exists enabled visible ready", timeout=20)
            continue_button.click()

        self.ui_supervisor.perform_action(
            select_controller, "host controller selection"
        )

        self.ui_supervisor.wait_for_text_and_click(
            "Do you want to continue with the host controller you have selected?",
            "Continue",
            "host controller confirmation",
        )
        self.ui_supervisor.wait_for_main_window("host controller confirmation")
        self.main_window = self.ui_supervisor.main_window
        self.log_window = self.ui_supervisor.log_window


    def select_test(self, test: int):
        """
        Selects a test from the CV Suite ListBox and sets a test description.

        Args:
            test (int):
                The numeric key from self.test_list that identifies
                the desired test (e.g., 6 for "Device Summary").

        Steps:
            - Finds the test in CV Suite's "ListBox" and highlights it.
            - If no tests have been run yet, sets the test description in the "Edit" control.
            - Clicks "Run" to start the test.
            - Waits for the device selection dialog and repeatedly attempts to find and
            select the correct device until successful.
        """
        # Compatibility entry point for callers using the former two-step API.
        return self.run_test(test)

        # Select the specified test from the CV Suite main window's ListBox.
        test_list_box = self.main_window.child_window(best_match="ListBox")
        test_list_box.select(test)

        # Click into the text field and set the test description if no prior tests are completed.
        test_description = self.main_window.child_window(best_match="Edit")
        test_description.set_focus()
        if (len(self.completed_test_list[self.usb_controller_name][2]) == 0
                and len(self.completed_test_list[self.usb_controller_name][3]) == 0):
            send_keys(self.test_description_input, with_spaces=True)

        # Click "Run" to proceed.
        self.main_window.child_window(best_match="Run").click()

        # Wait for the device selection dialog titled "USB Command Verifier (xHCI - USB 3)"
        device_list_outer_box = self.app.window(best_match=r"USB Command Verifier (xHCI - USB 3)")
        device_list_outer_box.wait('exists', timeout=20)

        # Within that dialog, find the ListBox of connected devices.
        device_list_box = device_list_outer_box.child_window(best_match="ListBox")

        device_found = False
        # Loop until the device is successfully found and selected.
        while not device_found:
            # print("Attempting to find and select the device...")

            # Check if the dialog is still there. If not, something else happened.
            if not device_list_outer_box.exists():
                logger.error("Device selection dialog disappeared unexpectedly. Aborting test.")
                # Exit the method since we can't proceed.
                return

            # Get the current list of devices from the GUI
            devices = device_list_box.texts()

            for index, item in enumerate(devices):
                if self.device.idVendor in item:
                    # print(f"Device found: {item}")
                    device_found = True
                    try:
                        # The 'index-1' logic is specific to how this ListBox enumerates items.
                        device_list_box.select(index - 1)
                        time.sleep(1) # A short pause for UI to update.
                        device_list_outer_box.child_window(best_match="Ok").click()
                    except Exception as e:
                        logger.exception(
                            "Error occurred while selecting the device or clicking OK: %s",
                            e,
                        )
                        # Reset device_found to False to ensure the loop retries.
                        device_found = False
                    # Exit the for loop since we've found our device (or tried to).
                    break

            if not device_found:
                # If the for loop completes and the device is still not found,
                # print a message and wait before the while loop tries again.
                logger.warning(
                    "DEVICE NOT FOUND. Please ensure the device is unlocked and "
                    "connected. Retrying in 15 seconds..."
                )
                time.sleep(15)
                # The 'while' loop will now repeat the entire check.


    def clear_dialog_boxes(self, test: int):
        """
        Clears CV Suite dialog boxes for a given test and processes test results.

        Args:
            test (int):
                The test ID to handle (e.g., 6 for "Device Summary").

        Steps:
            - Cycles through pre-defined 'dialog_strings' in self.test_list[test].
            - Waits for each dialog’s text, then clicks a button (often "OK").
            - Closes the final 'Results' dialog once the test is done.
            - Records the test outcome (Pass/Fail) into self.test_summary and writes
              to summary.json.
        """
        # Dialogs are now consumed by run_test/select_test.
        return None

        # For each dialog prompt in the test definition, wait for it and press the correct button.
        for key, value in self.test_list[test]["dialog_strings"].items():
            button_text = "OK"
            dialog_box = self.app.window(best_match=r"USB Command Verifier (xHCI - USB 3)")

            while True:
                if dialog_box.exists():
                    output = io.StringIO()
                    with redirect_stdout(output):
                        try:
                            dialog_box.print_control_identifiers()
                        except:
                            pass
                    window_test = output.getvalue()
                    target_string = value
                    if target_string in window_test:
                        time.sleep(1)
                        # Example overrides for certain test steps:
                        if test == 3 and key == 2:
                            button_text = "Yes"
                        elif test == 21 and key == 3:
                            button_text = "No"
                        # Execute the click, then break out to handle the next prompt.
                        dialog_box.child_window(best_match=button_text).click()
                        break

        # Once the test finishes, a "Results" dialog typically appears. Close it.
        results_dialog = self.app.window(best_match=r"Results")
        results_dialog.wait('exists', timeout=30, retry_interval=10)
        results_dialog.child_window(best_match="OK").click()

        # Mark the test as completed, storing pass/fail data.
        self.completed_test_list[self.usb_controller_name][self.usb_protocol].append(self.current_test)

        # Parse the log line (like "Tests run (20), Failures (0)") to gather numeric results.
        log_results = re.findall(r'\((.*?)\)', self.log_window.texts()[-2])
        log_results = [int(v) for v in log_results]
        # If zero failures, mark pass. Otherwise, fail.
        if log_results[1] == 0:
            log_results.append("Pass")
        else:
            log_results.append("Fail")

        # Ensure nested dictionaries are built in self.test_summary for Windows version, etc.
        # Then store the results for later reference.
        self.test_summary[f'Windows {self.windows_version}'][self.usb_controller_name][f'USB{self.usb_protocol}'][self.test_list[self.current_test]['name']].extend(log_results)

        # Dump the updated summary to the JSON file so progress is tracked.
        custom_json_dump(self.test_summary, self.destination_summary_json)

        # Print results to console as well.
        logger.info("--- %s: %s", self.test_list[self.current_test]["name"], log_results)


    def _dialog_rules(self, test: int) -> list[DialogRule]:
        rules = []
        for key, text in self.test_list[test]["dialog_strings"].items():
            button = "OK"
            if test == 3 and key == 2:
                button = "Yes"
            elif test == 21 and key == 3:
                button = "No"
            rules.append(DialogRule(key=key, text=text, button=button))
        return rules

    def _record_test_outcome(self, outcome: TestOutcome) -> None:
        completed = self.completed_test_list[self.usb_controller_name][self.usb_protocol]
        if self.current_test not in completed:
            completed.append(self.current_test)

        destination = self.test_summary[f'Windows {self.windows_version}'][self.usb_controller_name][f'USB{self.usb_protocol}'][self.test_list[self.current_test]['name']]
        destination[:] = outcome.summary_values()
        custom_json_dump(self.test_summary, self.destination_summary_json)
        logger.info(
            "--- %s: %s",
            self.test_list[self.current_test]["name"],
            outcome.summary_values(),
        )
        if outcome.reason:
            logger.info("    %s", outcome.reason)

    def _wait_for_device_after_failure(self) -> None:
        context = {
            "phase": "failure recovery",
            "test": self.current_test,
            "controller": self.usb_controller_name,
            "protocol": self.usb_protocol,
        }
        # CV Suite may leave its compliance driver applied after a failure. In
        # that state usb-windows.exe cannot see the DUT, so operator
        # acknowledgement is deliberately the recovery authority.
        self.ui_supervisor.operator_checkpoint(
            "The test failed. Power-cycle and unlock the DUT, then press ENTER.",
            context=context,
        )

    def run_test(self, test: int) -> TestOutcome:
        """Start, supervise, record, and recover a single CV Suite test."""
        if self.ui_supervisor is None:
            raise RuntimeError("CV Suite UI supervisor has not been initialized.")

        # The supervisor may have reconnected after an operator restarted CV Suite.
        self.app = self.ui_supervisor.app
        self.main_window = self.ui_supervisor.main_window
        self.log_window = self.ui_supervisor.log_window

        def start_test():
            baseline = tuple(self.log_window.texts())
            test_list_box = self.main_window.child_window(control_id=1001)
            test_list_box.wait("exists enabled visible ready", timeout=20)
            test_list_box.select(test)
            # CV Suite has multiple Edit controls. ID 1026 is the visible
            # Optional Test Description field; fuzzy matching selects a hidden
            # RichEdit control on this screen.
            test_description = self.main_window.child_window(control_id=1026)
            test_description.wait("exists enabled visible ready", timeout=20)
            test_description.set_focus()
            if (len(self.completed_test_list[self.usb_controller_name][2]) == 0
                    and len(self.completed_test_list[self.usb_controller_name][3]) == 0):
                send_keys(self.test_description_input, with_spaces=True)
            run_button = self.main_window.child_window(control_id=1013)
            run_button.wait("exists enabled visible ready", timeout=20)
            run_button.click()
            return baseline

        context = {
            "phase": "test execution",
            "test": test,
            "test_name": self.test_list[test]["name"],
            "controller": self.usb_controller_name,
            "protocol": self.usb_protocol,
        }
        while True:
            baseline_log = self.ui_supervisor.perform_action(
                start_test, "test launch", {"test": test}
            )
            outcome = self.ui_supervisor.monitor_test(
                self._dialog_rules(test),
                self.device.idVendor,
                self.device.idProduct,
                context,
                baseline_log,
            )
            if not outcome.retry_required:
                break
            logger.info("    %s", outcome.reason)
            self.ui_supervisor.operator_checkpoint(
                f"DUT VID {self.device.idVendor} / PID {self.device.idProduct} "
                "was not selected. Unlock that device, then press ENTER. "
                "The test will be reselected so CV Suite rescans the bus.",
                context=context,
            )
            self.ui_supervisor.prepare_for_test_retry(context)

        self._record_test_outcome(outcome)
        if outcome.failed:
            self._wait_for_device_after_failure()
        return outcome

    def close_cv_suite(self):
        """
        Closes the CV Suite application’s main window.

        A short pause is performed prior to close. This finalizes the workflow
        if the script ends or if we switch controllers/protocols.
        """
        time.sleep(1)
        if self.ui_supervisor is not None:
            self.main_window = self.ui_supervisor.main_window
        try:
            if self.main_window is not None and self.main_window.exists(timeout=2):
                self.main_window.close()
        except Exception as exc:
            logger.exception("Warning: CV Suite could not be closed cleanly: %s", exc)
