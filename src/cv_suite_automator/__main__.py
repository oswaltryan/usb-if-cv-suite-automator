from .core import *

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
    print("""
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
    print(f"- {cv_suite.usb_controller_name}")

    # Start the CV Suite, select the current controller.
    cv_suite.start_cv_suite()
    
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
        controller.turn_on('usb3')

    # Switch from ASMedia -> Intel or Intel -> ASMedia for the second run.
    if not controller_switched:
        # Determine the new target controller
        if cv_suite.usb_controller_name == "ASMedia":
            new_controller_name = "Intel"
            new_controller_index = 2
        else:
            new_controller_name = "ASMedia"
            new_controller_index = 0
        
        # Power cycle the device port to ensure a clean re-detection
        controller.turn_off('power')
        time.sleep(1)
        controller.turn_on('usb3')
        controller.turn_on('power')

        print("\n" + "="*70)
        print(f"ACTION REQUIRED: Please move the device to a '{new_controller_name}' USB port.")
        print("The script will continue automatically once the device is detected on the correct controller.")
        print("="*70)

        while True:
            # Use the find_apricorn_device utility to see what's connected
            device = find_apricorn_device()
            
            if device:
                # A device was found. Check if it's on the correct controller.
                # Note: find_apricorn_device returns a list, so we check the first element.
                detected_controller = device[0].usbController
                if detected_controller == new_controller_name:
                    print(f"Success! Device detected on the '{new_controller_name}' controller. Proceeding...")
                    break  # The device is on the new controller, exit the loop
                else:
                    # The device is connected, but still on the old controller.
                    print(f"Device is still on the '{detected_controller}' port. Please move it to '{new_controller_name}'. Retrying in 5 seconds...")
                    time.sleep(5)
            else:
                # No device is detected at all.
                print(f"Waiting for device to be connected to the '{new_controller_name}' port... Retrying in 5 seconds...")
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
    print("\n" + "="*70)
    print(f"OPERATING SYSTEM (Windows {cv_suite.windows_version}) TEST COMPLETE.")
    print("To finish the test session, please do the following:")
    print("1. Reboot into the other operating system.")
    print("2. Run the script again with the same command:")
    print(f"   python cv_suite_automation.py \"{sys.argv[1]}\"")
    print("The script will automatically find and continue this session.")
    print("="*70 + "\n")
else:
    print("\n" + "="*70)
    print("BOTH OPERATING SYSTEMS HAVE BEEN TESTED.")
    print(f"Test session '{cv_suite.test_datetime}' is now complete.")
    print(f"Final results are in: {cv_suite.destination_summary_json}")
    print("="*70 + "\n")