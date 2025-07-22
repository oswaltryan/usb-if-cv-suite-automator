@echo off
:: =========================================================================
:: system_setup.bat (Task Scheduler - Corrected Version)
:: -------------------------------------------------------------------------
:: This version creates a valid ONLOGON task by removing the unsupported
:: /sd (Start in) parameter. It relies on the launcher script to set its
:: own working directory.
::
:: This script MUST be run with Administrator privileges.
:: =========================================================================

echo.
echo  =======================================
echo   CV Suite Automation - System Setup
echo  =======================================
echo.
echo  This script will now configure an interactive scheduled task.
echo  Administrator privileges are required.
echo.
echo  --- Execution Log ---

:: --- (1) SCRIPT SETUP ---
set "DRIVE_LETTER=Z"
for %%I in ("%~dp0\..") do set "PROJECT_ROOT=%%~fI"
set "LAUNCHER_SCRIPT_PATH=%~dp0task_scheduler_launcher.bat"
set "TASK_NAME=CV Suite Autostart Agent"

echo.
echo [INFO] Project Root detected as: "%PROJECT_ROOT%"
echo [INFO] Launcher Script Path set to: "%LAUNCHER_SCRIPT_PATH%"
echo.

:: --- (2) PRE-CHECKS ---
echo [1/3] Checking for External Results Drive (%DRIVE_LETTER%:)...
if exist "%DRIVE_LETTER%:\" (
    echo      [SUCCESS] Drive %DRIVE_LETTER%: found.
) else (
    echo.
    echo      !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
    echo      !! [ERROR] Drive %DRIVE_LETTER%: not found. Aborting.   !!
    echo      !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
    echo.
    goto :EndScript
)
echo.

:: --- (3) FULL CLEANUP ---
echo [2/3] Cleaning up all old startup methods...
set "OLD_SHORTCUT_PATH=%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup\CV Suite Automation Agent.lnk"
if exist "%OLD_SHORTCAT_PATH%" ( del "%OLD_SHORTCUT_PATH%" )
schtasks /delete /tn "%TASK_NAME%" /f > nul 2>&1
echo      [SUCCESS] Cleanup complete.
echo.

:: --- (4) DEPLOY new INTERACTIVE Task ---
echo [3/3] Deploying new Interactive Task via Task Scheduler...

if not exist "%LAUNCHER_SCRIPT_PATH%" (
    echo [ERROR] The launcher script is missing at "%LAUNCHER_SCRIPT_PATH%".
    goto :EndScript
)

echo      Creating new scheduled task: "%TASK_NAME%"

:: vvvvvvvvvvvvvvv THE FIX IS HERE vvvvvvvvvvvvvvvvvvv
:: Removed the invalid /sd parameter to make the command valid for ONLOGON tasks.
schtasks /create /tn "%TASK_NAME%" /tr "%LAUNCHER_SCRIPT_PATH%" /sc onlogon /rl HIGHEST /f
:: ^^^^^^^^^^^^^^^^^^^^ THE FIX IS HERE ^^^^^^^^^^^^^^^^^^^^

if %errorlevel% neq 0 (
    echo.
    echo      !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
    echo      !! [FATAL ERROR] Failed to create the scheduled task.       !!
    echo      !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
) else (
    echo      [SUCCESS] Interactive scheduled task created successfully.
)
echo.

:EndScript
echo =======================================
echo  Setup script has finished.
echo =======================================
echo.
pause