@echo off
:: =========================================================================
:: system_setup.bat
:: -------------------------------------------------------------------------
:: This script performs one-time configuration for the CV Suite Automator.
:: It verifies the external results drive is present and deploys the
:: autostart agent to the user's Startup folder.
::
:: This script should be run with Administrator privileges if possible.
:: =========================================================================

:: --- (1) SCRIPT SETUP (No edits needed) ---
set "DRIVE_LETTER=Z"
set "PROJECT_ROOT=%~dp0.."
set "AGENT_SCRIPT_NAME=autostart_cv_suite_testing.bat"
set "AGENT_SCRIPT_PATH=%PROJECT_ROOT%\scripts\%AGENT_SCRIPT_NAME%"
set "STARTUP_FOLDER=%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup"
set "SHORTCUT_NAME=CV Suite Automation Agent.lnk"
set "SHORTCUT_PATH=%STARTUP_FOLDER%\%SHORTCUT_NAME%"


:: --- (2) EXECUTION ---
echo.
echo  CV Suite Automation - System Setup
echo  ------------------------------------
echo  This script will perform the following actions:
echo    1. Check for the external results drive at %DRIVE_LETTER%:
echo    2. Create a shortcut to the autostart agent in your Startup folder.
echo.
pause


:: Action 1: Check for External Drive
echo [1/2] Checking for External Drive...
if exist %DRIVE_LETTER%:\ (
    echo      SUCCESS: Drive %DRIVE_LETTER%: found.
) else (
    echo.
    echo      !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
    echo      !! ERROR: Drive %DRIVE_LETTER%: not found.                            !!
    echo      !! Please plug in your external results drive and ensure    !!
    echo      !! Windows has assigned it the letter %DRIVE_LETTER%:.                  !!
    echo      !! You may need to use Disk Management to set the letter.   !!
    echo      !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
    echo.
    pause
    goto :eof
)
echo.


:: Action 2: Deploy Autostart Agent
echo [2/2] Deploying Autostart Agent...
if not exist "%AGENT_SCRIPT_PATH%" (
    echo ERROR: Could not find the agent script at the expected location.
    goto :eof
)

if exist "%SHORTCUT_PATH%" (
    echo      INFO: Shortcut already exists in Startup folder. Skipping.
) else (
    echo      Creating shortcut...
    powershell.exe -Command "$ws = New-Object -ComObject WScript.Shell; $s = $ws.CreateShortcut('%SHORTCUT_PATH%'); $s.TargetPath = '%AGENT_SCRIPT_PATH%'; $s.Save()"
    if exist "%SHORTCUT_PATH%" (
        echo      SUCCESS: Shortcut created successfully.
    ) else (
        echo      ERROR: Failed to create the shortcut. Please try creating it manually.
    )
)
echo.


echo.
echo Setup script complete.
echo.