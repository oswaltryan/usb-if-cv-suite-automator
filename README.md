# CV Suite Automation

This project provides a suite of Python scripts and orchestration tools to automate USB-IF compliance testing using the "USB 3 Gen X Command Verifier" (CV Suite) application on Windows. It is designed to run a full test matrix across different USB host controllers (e.g., ASMedia, Intel), USB protocols (2.0 and 3.0), and operating systems (Windows 10 and 11).

The system is designed as a semi-automated workflow, handling all software and OS-level orchestration, but requiring a single manual hardware intervention during the test run on each OS.

## Project Structure

The project follows a modern Python structure to ensure clarity, maintainability, and testability.

```
cv_suite_testing/
├── README.md
├── requirements.txt
├── setup.py
├── wheels/                            # Pre-compiled offline dependencies
│
├── scripts/                           # Orchestration and setup scripts
│   ├── start_cv_suite_session.bat     # INITIATOR: Kicks off the full, two-OS test run.
│   ├── run_automation.bat             # EXECUTOR: Runs a single-OS test; handles venv.
│   ├── autostart_cv_suite_testing.bat # CONTINUATION AGENT: Runs automatically after reboot.
│   ├── system_setup.bat               # HELPER: Assists with one-time system configuration.
│   └── toggle_windows_version.ps1     # UTILITY: Reboots the machine to the other OS.
│
├── src/
│   └── cv_suite_automator/            # The main Python package
│       └── ... (package contents) ...
│
└── venv/                              # Isolated Python environment
```

## Prerequisites

### Hardware
- A test PC with **both Windows 10 and Windows 11** installed in a dual-boot configuration.
- The USB Device Under Test (DUT), e.g., an Apricorn encrypted drive.
- An **external hard drive or SSD** for storing test results.
- A **Phidgets IO Controller** and a corresponding USB 2.0/3.0 switchboard.
- Necessary cables to connect the switchboard to **both an ASMedia and an Intel USB 3.x port** on the motherboard.

### Software
- **Python 3.12** or later.
- **Git** for cloning the repository.
- The **USB-IF "USB 3 Gen X Command Verifier"** application installed on *both* operating systems.

## System Setup & Commissioning (One-Time Only)

The following steps must be performed on **both** the Windows 10 and Windows 11 partitions to prepare the test environment.

1.  **Clone the Repository:**
    ```bash
    git clone <your-repo-url> C:\cv_suite_testing
    cd C:\cv_suite_testing
    ```

2.  **Create Virtual Environment and Install Dependencies:**
    This process creates an isolated environment for the project and installs all necessary packages.
    ```powershell
    # Create the virtual environment
    python -m venv venv

    # Activate it just for this setup process
    .\venv\Scripts\activate

    # Install dependencies from the requirements file
    pip install -r requirements.txt

    # Deactivate when done
    deactivate
    ```

3.  **System Configuration & Agent Deployment:**
    You must configure the system to recognize the results drive and deploy the autostart script. You can do this manually or with the provided setup script. Choose one method.

    ---
    ### Method A: Manual Setup
    1.  **Prepare External Drive:** Plug in your external results drive. Open **Disk Management** in Windows and ensure the drive is assigned the letter **`Z:`**. This is required for the scripts to find it.
    2.  **Deploy Autostart Agent:**
        - Right-click on `C:\cv_suite_testing\scripts\autostart_cv_suite_testing.bat`.
        - Select **"Create shortcut"**.
        - Open the Windows Startup folder by pressing `Win + R`, typing `shell:startup`, and hitting Enter.
        - Move the newly created shortcut into this Startup folder.
    3.  **Disable Windows Login:** For the automated cross-OS reboot to work, you must manually disable the password requirement for login.

    ---
    ### Method B: Assisted Scripted Setup
    A script is provided to assist with the setup.

    1.  **Prepare External Drive:** Plug in your external results drive and ensure Windows has assigned it the letter **`Z:`**.
    2.  **Run the Setup Script:** Right-click `C:\cv_suite_testing\scripts\system_setup.bat` and select **"Run as administrator"**. The script will verify that the `Z:` drive exists and deploy the autostart agent shortcut for you.
    3.  **Disable Windows Login:** The script **cannot** perform this step. You must still manually disable the password requirement for login for the cross-OS automation to work.
    ---

## Workflow & Usage

The project provides two distinct workflows for running tests. You do not need to activate the virtual environment for either method, as the scripts handle it automatically.

### Fully Automated Workflow (Recommended)

Use this method to run the complete test suite across both operating systems.

1.  **Connect the DUT:** Plug the **unlocked** Device Under Test into the USB switchboard port corresponding to the first controller to be tested (e.g., ASMedia).

2.  **Initiate the Session:** Open a Command Prompt or PowerShell and run the **`start_cv_suite_session.bat`** script. Pass the bridge controller chipset as an argument.
    ```powershell
    C:\cv_suite_testing\scripts\start_cv_suite_session.bat "3861EN-FL"
    ```
    This script will run the tests on the current OS, and then automatically reboot the machine to continue.

3.  **Perform the Physical Controller Switch:**
    The automation will pause **once per operating system** and prompt you in the console:
    > **REQUIRED INTERVENTION:** When you see the prompt `Connect device to <Other> USB Controller`, you must physically move the DUT's cable to the other controller's port on the switchboard and press **Enter** to continue.

4.  **Completion:** The process finishes automatically after the tests on the second OS are complete. Final results are stored on the `Z:` drive.

### Manual Workflow (Single OS Spot-Check)

Use this method for debugging or running tests on a single OS without triggering a reboot.

1.  **Connect the DUT:** Plug the unlocked device into the desired controller port.
2.  **Run the Launcher Script:** From a Command Prompt or PowerShell, run the **`run_automation.bat`** script, passing the chipset as an argument.
    ```powershell
    C:\cv_suite_testing\scripts\run_automation.bat "3861EN-FL"
    ```
    The script will complete all tests for the current OS and then exit.

## Known Limitations

The primary manual step in the automated workflow is the physical switching of the DUT between host controller ports. To achieve true "lights-out" automation, this would need to be replaced by a **programmable USB A/B switch** (e.g., from vendors like Acroname or MCCI) that can be controlled by the Python script.