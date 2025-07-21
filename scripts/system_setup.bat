@echo off
:: =========================================================================
:: system_setup.bat
:: -------------------------------------------------------------------------
:: This script performs one-time configuration for the CV Suite Automator.
:: It uses the Task Scheduler for reliable startup on both Win 10 and Win 11.
::
:: This script MUST be run with Administrator privileges.
:: =========================================================================

:: --- (1) SCRIPT SETUP (No edits needed) ---
set "DRIVE_LETTER=Z"
for %%I in ("%~dp0\..") do set "PROJECT_ROOT=%%~fI"
set "AGENT_SCRIPT_NAME=autostart_cv_suite_testing.bat"
set "AGENT_SCRIPT_PATH=%PROJECT_ROOT%\scripts\%AGENT_SCRIPT_NAME%"
set "TASK_NAME=CV Suite Autostart Agent"


:: --- (2) EXECUTION ---
echo.
echo  CV Suite Automation - System Setup
echo  ------------------------------------
echo  This script will perform the following actions:
echo    1. Check for the external results drive at %DRIVE_LETTER%:
echo    2. Create a Scheduled Task to run the autostart agent on logon.
echo.
echo  This script requires Administrator privileges to create the task.
pause


:: Action 1: Check for External Drive
echo [1/3] Checking for External Drive...
if exist %DRIVE_LETTER%:\ (
    echo      SUCCESS: Drive %DRIVE_LETTER%: found.
) else (
    echo.
    echo      !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
    echo      !! ERROR: Drive %DRIVE_LETTER%: not found.                            !!
    echo      !! Please plug in your external results drive and ensure    !!
    echo      !! Windows has assigned it the letter %DRIVE_LETTER%:.                  !!
    echo      !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
    echo.
    pause
    goto :eof
)
echo.


:: Action 2: Clean up old startup methods
echo [2/3] Cleaning up old startup methods (if they exist)...
set "OLD_SHORTCUT_PATH=%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup\CV Suite Automation Agent.lnk"
if exist "%OLD_SHORTCUT_PATH%" (
    echo      Deleting old startup shortcut...
    del "%OLD_SHORTCUT_PATH%"
)
echo      Checking for and deleting any pre-existing scheduled task...
schtasks /delete /tn "%TASK_NAME%" /f > nul 2>&1
echo      Cleanup complete.
echo.


:: Action 3: Deploy Autostart Agent via Task Scheduler
echo [3/3] Deploying Autostart Agent via Task Scheduler for reliable startup...
if not exist "%AGENT_SCRIPT_PATH%" (
    echo ERROR: Could not find the agent script at the expected location.
    goto :eof
)

echo      Creating new scheduled task: "%TASK_NAME%"
:: vvvvvvvvvvvvvvv THE FIX IS HERE vvvvvvvvvvvvvvvvvvv
:: This command creates a task that runs on user logon.
:: It launches Windows Terminal (wt.exe) and passes our script to it.
:: /ru "SYSTEM" and /rl HIGHEST ensure it runs with proper privileges.
schtasks /create /tn "%TASK_NAME%" /tr "wt.exe -d \"%PROJECT_ROOT%\" \"%AGENT_SCRIPT_PATH%\"" /sc onlogon /ru "SYSTEM" /rl HIGHEST /f

if %errorlevel% neq 0 (
    echo.
    echo      ERROR: Failed to create the scheduled task. Please ensure you
    echo      are running this script as an Administrator.
) else (
    echo      SUCCESS: Scheduled Task created successfully.
    echo      The automation agent will now run on the next user logon.
)
:: ^^^^^^^^^^^^^^^^^^^^ THE FIX IS HERE ^^^^^^^^^^^^^^^^^^^^
echo.


echo.
echo Setup script complete.
echo.
pause