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
├── wheels/                             # Pre-compiled offline dependencies
│
├── scripts/
│   ├── setup_environment.bat           # SETUP: Creates the Python virtual environment and installs all dependencies from the offline 'wheels' folder.
│   ├── system_setup.bat                # SETUP: Configures Windows settings (checks for the Z: drive, deploys the startup agent).
│   │
│   ├── start_cv_suite_session.bat      # RUNNER (Full Auto): Kicks off the complete, two-OS test run. This is the main entry point for a full session.
│   ├── run_automation.bat              # RUNNER (Manual): Executes a single-OS test run for debugging. It is called by the other runner scripts.
│   │
│   ├── autostart_cv_suite_testing.bat  # AGENT: Runs automatically after a reboot to continue a test session. It is deployed by system_setup.bat.
│   └── toggle_windows_version.ps1      # UTILITY: A PowerShell script used internally by start_cv_suite_session.bat to reboot the machine to the other OS.
│
├── src/
│   └── cv_suite_automator/             # The main Python package
│       └── ... (package contents) ...
│
└── venv/                               # Isolated Python environment
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

The following steps must be performed in order on **both** the Windows 10 and Windows 11 partitions to prepare the test environment.

### Step 1: Get the Project Code
Clone this repository to your machine.
```bash
git clone <your-repo-url> C:\cv_suite_testing
cd C:\cv_suite_testing
``` 

### Step 2: Set Up the Python Environment
This step creates an isolated Python environment for the project and installs all its dependencies from the local `wheels` folder, allowing for a completely offline setup.

**DO NOT RUN AS ADMINISTRATOR PRIVILIGES**
```powershell
# Run the environment setup script from the project root
.\scripts\setup_environment.bat
```

### Step 3: Configure the Windows System
This step ensures your Windows environment is correctly configured for the automation. It checks for the results drive and deploys the agent that continues the test after a reboot. You can do this manually or with the provided script.

#### Method A: Manual Configuration
1.  **Prepare External Drive:** Plug in your external results drive. Open **Disk Management** in Windows and ensure the drive is assigned the letter **`Z:`**. This is required for the scripts to find it.
2.  **Deploy Autostart Agent:**
    - Right-click on `C:\cv_suite_testing\scripts\autostart_cv_suite_testing.bat`.
    - Select **"Create shortcut"**.
    - Open the Windows Startup folder by pressing `Win + R`, typing `shell:startup`, and hitting Enter.
    - Move the newly created shortcut into this Startup folder.
3.  **Disable Windows Login:** Extract and install `AutoLogon.exe`.

#### Method B: Assisted Scripted Configuration
A script is provided to assist with the setup.

1.  **Prepare External Drive:** First, plug in your external results drive and ensure Windows has assigned it the letter **`Z:`**.
2.  **Run the Setup Script:** Right-click `C:\cv_suite_testing\scripts\system_setup.bat` and select **"Run as administrator"**. The script will verify that the `Z:` drive exists and deploy the autostart agent shortcut for you.
3.  **Disable Windows Login:** Extract and install `AutoLogon.exe`.

## Workflow & Usage

### Fully Automated Workflow (Recommended)
Use this method to run the complete test suite across both operating systems.

1.  **Connect the DUT:** Plug the **unlocked** Device Under Test into the USB switchboard port corresponding to the first controller to be tested (e.g., ASMedia).

2.  **Initiate the Session:** Open a Command Prompt or PowerShell and run the **`start_cv_suite_session.bat`** script. This is the main entry point for a full test. It works by calling `run_automation.bat` to execute the tests, and then calls `toggle_windows_version.ps1` to reboot.
    ```powershell
    C:\cv_suite_testing\scripts\start_cv_suite_session.bat "3861EN-FL"
    ```

3.  **Perform the Physical Controller Switch:**
    The automation will pause **once per operating system** and prompt you in the console:
    > **REQUIRED INTERVENTION:** When you see the prompt `Connect device to <Other> USB Controller`, you must physically move the DUT's cable to the other controller's port on the switchboard and press **Enter** to continue.

### Manual Workflow (Single OS Spot-Check)
Use this method for debugging or running tests on a single OS without triggering a reboot.

1.  **Connect the DUT:** Plug the unlocked device into the desired controller port.
2.  **Run the Launcher Script:** From a Command Prompt or PowerShell, run the **`run_automation.bat`** script. This script's primary job is to activate the virtual environment and execute the Python code.
    ```powershell
    C:\cv_suite_testing\scripts\run_automation.bat "3861EN-FL"
    ```

## Known Limitations

The primary manual step in the automated workflow is the physical switching of the DUT between host controller ports. This will be eliminated by integrating a programmable Acroname USB hub in a future update.