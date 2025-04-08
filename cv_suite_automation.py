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

Functions:
    pull_files:
        A utility function to copy or move generated CV Suite files from
        the source directory to a designated destination (imported from
        `organizer`).

Usage:
    Run the script with the following argument:
        1) A string specifying the Bridge Controller Chipset, e.g.
           3861EN-FL or 3639EN-FL.

Example:
    python cv_suite_automation.py 3861EN-FL
"""

import json
import os
import io
import re
import sys
import time
import shutil
import platform

from contextlib import redirect_stdout
from pprint import pprint
from pywinauto import Application
from pywinauto.keyboard import send_keys

# These are local imports in your environment:
from organizer import *
from usb-tool import *
from json_encoder import *
from phidget_board import IOController

controller = IOController()              # Initialize controller
controller.turn_on('power')               # Turn on power (channel 13)
controller.turn_on('usb3')                # Turn on USB3 (channel 14)
input(f"Plug device in USB2/3 switchboard and unlock. Press enter to continue")
time.sleep(5)


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

        select_test(test: int):
            Selects a test by ID in the CV Suite ListBox and sets up
            the test description in the UI.

        clear_dialog_boxes(test: int):
            Looks for CV Suite dialog boxes related to the currently running
            test, clicks through them, and processes the results.

        close_cv_suite():
            Closes the CV Suite main window.

    Example:
        cv_suite = CVSuiteAutomation()
        cv_suite.start_cv_suite()
        cv_suite.select_test(6)
        cv_suite.clear_dialog_boxes(6)
        cv_suite.close_cv_suite()
    """

    def __init__(self):
        """
        Initializes the CVSuiteAutomation class with user inputs and default configurations.

        This method:
          1) Detects an attached Apricorn device (via find_apricorn_device).
          2) Infers the 'usb_controller_name' and 'usb_controller' from the device.
          3) Determines the Windows version and sets 'windows_user_name'.
          4) Builds file paths for storing CV Suite results.
          5) Reads and stores the test parameter from sys.argv.
          6) Prepares data structures for test management (test_list, completed_test_list, etc.).
        """

        # Attempt to locate a recognized Apricorn device (custom function).
        self.device = find_apricorn_device()
        if self.device is None:
            print("No device found.")
            sys.exit(1)  # Exit if no device is found.
        else:
            pprint(self.device)
            input(f"Check devices:")

        # Use the device’s USB controller name to determine the integer index for CV Suite’s UI.
        self.usb_controller_name = self.device.usbController
        if self.usb_controller_name == "ASMedia":
            self.usb_controller = 0
        else:
            self.usb_controller = 2

        # Detect Windows version (10 or 11) and set user name accordingly.
        self.windows_version = int(platform.win32_ver()[0])
        if self.windows_version == 10:
            self.windows_user_name = "Testing"
        elif self.windows_version == 11:
            self.windows_user_name = "itadmin"

        # Create a timestamp for test-labelling in directories.
        self.test_datetime = time.strftime("%Y-%m-%d %H%M", time.localtime())

        # sys.argv[1] is expected to be the "bridge controller chipset" string.
        # We also append the device model name (self.device.iProduct).
        self.test_description_input = sys.argv[1] + " " + self.device.iProduct

        # bcdUSB might look like "3.2" => self.usb_protocol = 3
        self.usb_protocol = int(self.device.bcdUSB[0])

        # Build the paths for the source/destination of the test results.
        self.source_reports_dir = (
            f'C:\\Users\\{self.windows_user_name}\\Documents\\USB-IF Test Suite\\CV Reports\\USB3CV'
        )
        self.source_summary_json = (
            f'C:\\Users\\{self.windows_user_name}\\Desktop\\cv_suite_testing\\summary_template.json'
        )
        self.destination_drive = 'Z:\\USB-IF Results'  # Adjust if needed.
        self.destination_reports_dir = (
            f'{self.destination_drive}\\{self.test_description_input}\\'
            f'v{self.device.bcdDevice}\\{self.device.driveSize}GB\\'
            f'{self.test_datetime}\\Windows {self.windows_version}'
        )
        self.destination_summary_json = f'{self.destination_reports_dir}\\summary.json'

        # Initialize pywinauto objects
        self.app = None
        self.main_window = None
        self.log_window = None
        self.current_test = None

        # List of tests we might execute. For brevity, only test #6 is shown below.
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

        # Check if device is UASP
        if self.device.SCSIDevice == 'True':
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
        time.sleep(1)  # Short pause to allow the app to start.

        # Connect to the application and get references to key windows/controls.
        self.app = Application().connect(title=r"USB 3 Gen X Command Verifier")
        self.main_window = self.app.window(best_match=r"USB 3 Gen X Command Verifier")
        self.log_window = self.main_window.child_window(best_match="Edit2")

        # Select the USB controller index in the ListBox UI.
        list_box = self.main_window.child_window(best_match="ListBox")
        list_box.select(self.usb_controller)

        # Press 'Continue' to proceed.
        self.main_window.child_window(best_match="Continue").click()

        # Wait for the "confirm host controller" prompt and press 'Continue' there as well.
        while True:
            if self.main_window.exists():
                output = io.StringIO()
                with redirect_stdout(output):
                    try:
                        self.main_window.print_control_identifiers()
                    except:
                        pass
                window_test = output.getvalue()
                target_string = "Do you want to continue with the host controller you have selected?"
                if target_string in window_test:
                    time.sleep(1)
                    self.main_window.child_window(best_match="Continue").click()
                    break


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
            - Waits for the device selection dialog, then picks the correct device
              (based on the device's vendor ID).
        """
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

        # Attempt to find the target device by matching the vendor ID.
        devices = device_list_box.texts()
        device_found = False
        for index, item in enumerate(devices):
            if self.device.idVendor in item:
                device_found = True
                # The 'index-1' logic may be specific to how the ListBox enumerates items.
                device_list_box.select(index - 1)
                time.sleep(3)  # brief delay for selection
                device_list_outer_box.child_window(best_match="Ok").click()
                break

        # If not found, prompt user to fix the connection.
        if not device_found:
            input("DEVICE NOT FOUND. RESTART TEST, ENSURE DEVICE IS UNLOCKED, "
                  "AND CONNECTED TO THE CORRECT CONTROLLER, THEN PRESS ENTER.")


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
        print(f"--- {self.test_list[self.current_test]['name']}: {log_results}")


    def close_cv_suite(self):
        """
        Closes the CV Suite application’s main window.

        A short pause is performed prior to close. This finalizes the workflow
        if the script ends or if we switch controllers/protocols.
        """
        time.sleep(1)
        self.main_window.close()


########################################################
#                 Start the Program                    #
########################################################
if __name__ == "__main__":
    """
    Main entry point of the CV Suite automation script.

    - Validates that one argument is passed (bridge controller chipset).
    - Creates a CVSuiteAutomation instance and orchestrates the test flows
      for USB controllers (e.g., ASMedia / Intel) under both USB protocols
      (2 and 3).
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
        print("""
One argument is required for this program:
    1 - (str) Bridge Controller Chipset
        """)
        sys.exit(1)

    # Create an automation object.
    cv_suite = CVSuiteAutomation()

    # Attempt to run the test suite across both controllers (ASMedia and Intel).
    controller_switched = False

    # We loop twice—once for the current usb_controller_name, once after switching to the other.
    for i in range(2):
        print(f"- {cv_suite.usb_controller_name}")

        # Start the CV Suite, select the current controller, and create the reports directory.
        cv_suite.start_cv_suite()
        if not os.path.exists(cv_suite.destination_reports_dir):
            os.makedirs(cv_suite.destination_reports_dir)

            # Copy the template summary JSON into the new directory.
            shutil.copy(src=cv_suite.source_summary_json, dst=cv_suite.destination_summary_json)

            # Load it into our test_summary structure.
            with open(cv_suite.destination_summary_json) as jsonFile:
                cv_suite.test_summary = json.load(jsonFile)

        # We manage USB 2 vs. USB 3 protocols in another loop.
        protocol_switched = False
        for _ in cv_suite.completed_test_list[cv_suite.usb_controller_name]:
            print(f"-- USB{cv_suite.usb_protocol}")

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
                cv_suite.select_test(test=key)
                cv_suite.clear_dialog_boxes(test=key)

                # Check for certain known failure messages.
                for items in cv_suite.failure_messages:
                    confirm_DUT_presence = cv_suite.main_window.child_window(best_match='Validating')
                    if not confirm_DUT_presence:
                        print("\nTest Information:")
                        print("test_datetime", cv_suite.test_datetime)
                        print("test_description_input", cv_suite.test_description_input)
                        print("completed_test_list", cv_suite.completed_test_list)

            # Move or copy the test reports to our designated folder structure.
            pull_files(
                source=cv_suite.source_reports_dir,
                dest=f"{cv_suite.destination_reports_dir}\\{cv_suite.usb_controller_name}\\USB{cv_suite.usb_protocol}",
                fallback=f"C:\\Users\\{cv_suite.windows_user_name}\\Desktop\\CV Reports"
            )

            # Switch from USB2 to USB3 or vice versa after the first set of tests.
            if not protocol_switched:
                if cv_suite.usb_protocol == 2:
                    cv_suite.usb_protocol += 1  # Switch from USB2 -> USB3
                else:
                    cv_suite.usb_protocol -= 1  # Switch from USB3 -> USB2
                # input(f"Connect device USB{cv_suite.usb_protocol} and press Enter to continue")
                controller.turn_off('usb3')               # Turn off USB3 (channel 14)
                time.sleep(5)
                protocol_switched = True

        # Close the CV Suite application.
        cv_suite.close_cv_suite()

        # Switch from ASMedia -> Intel or Intel -> ASMedia for the second run.
        if not controller_switched:
            if cv_suite.usb_controller_name == "ASMedia":
                cv_suite.usb_controller_name = "Intel"
                cv_suite.usb_controller = 2
            else:
                cv_suite.usb_controller_name = "ASMedia"
                cv_suite.usb_controller = 0
            cv_suite.usb_protocol = 3
            controller_switched = True

            # Prompt the user to physically move the device to the other USB controller.
            controller.turn_off('power')               # Turn off power (channel 13)
            time.sleep(1)
            controller.turn_on('usb3')
            controller.turn_on('power')
            input(f"Connect device to {cv_suite.usb_controller_name} USB Controller")

            protocol_switched = False
