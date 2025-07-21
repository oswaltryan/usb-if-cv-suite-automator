@echo off
:: =========================================================================
:: system_setup.bat (Final Version)
:: -------------------------------------------------------------------------
:: This script uses dedicated helper files for reliability:
::  - create_shortcut.ps1: Creates the .lnk file.
::  - launch_in_terminal.bat: Ensures the agent runs in Windows Terminal.
::
:: This script MUST be run with Administrator privileges.
:: =========================================================================

echo.
echo  =======================================
echo   CV Suite Automation - System Setup
echo  =======================================
echo.
echo  This script will now attempt to configure the system.
echo  Administrator privileges are required.
echo.
echo  --- Execution Log ---

:: --- (1) SCRIPT SETUP ---
set "DRIVE_LETTER=Z"
for %%I in ("%~dp0\..") do set "PROJECT_ROOT=%%~fI"
set "TASK_NAME=CV Suite Autostart Agent"
echo.
echo [INFO] Project Root detected as: "%PROJECT_ROOT%"
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

:: --- (3) CONFIGURATION ---
echo [2/3] Cleaning up old Scheduled Task (if it exists)...
schtasks /delete /tn "%TASK_NAME%" /f > nul 2>&1
echo      [SUCCESS] Old task cleanup command sent.
echo.

echo [3/3] Deploying Autostart Agent via Startup Folder...
set "LAUNCHER_SCRIPT_PATH=%~dp0launch_in_terminal.bat"
set "HELPER_SCRIPT_PATH=%~dp0create_shortcut.ps1"
set "SHORTCUT_PATH=%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup\CV Suite Automation Agent.lnk"

if not exist "%HELPER_SCRIPT_PATH%" (
    echo [ERROR] Missing helper script: create_shortcut.ps1. Aborting.
    goto :EndScript
)
if not exist "%LAUNCHER_SCRIPT_PATH%" (
    echo [ERROR] Missing launcher script: launch_in_terminal.bat. Aborting.
    goto :EndScript
)

echo      [INFO] Calling PowerShell to create shortcut to the terminal launcher...
powershell.exe -ExecutionPolicy Bypass -File "%HELPER_SCRIPT_PATH%" -ShortcutPath "%SHORTCUT_PATH%" -TargetPath "%LAUNCHER_SCRIPT_PATH%" -WorkingDirectory "%PROJECT_ROOT%"

if %errorlevel% neq 0 (
    echo      !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
    echo      !! [FATAL ERROR] PowerShell failed to create the shortcut.  !!
    echo      !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
) else (
    echo      [SUCCESS] Startup shortcut has been created successfully.
)
echo.

:EndScript
echo =======================================
echo  Setup script has finished.
echo =======================================
echo.
pause