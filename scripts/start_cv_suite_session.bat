@echo off
:: =========================================================================
:: start_cv_suite_session.bat
:: -------------------------------------------------------------------------
:: Kicks off the full, two-OS test automation.
:: This script creates a flag file, calls the main runner, and then
:: initiates a reboot to the other OS.
:: =========================================================================

:: --- 1. Validate Input ---
if "%~1"=="" (
    echo ERROR: Missing argument.
    echo.
    echo Usage: %~n0 "bridge_controller_chipset"
    echo Example: %~n0 "3861EN-FL"
    goto :eof
)

set "CHIPSET_ARG=%~1"
set "PROJECT_ROOT=%~dp0.."
set "FLAG_FILE=%PROJECT_ROOT%\test_in_progress.flag"
set "REBOOT_SCRIPT=%~dp0toggle_windows_version.ps1"

echo =================================================
echo  CV Suite Automation - Full Session Initiator
echo =================================================
echo.
echo [1/3] Creating automation "baton" for the next OS...
echo %CHIPSET_ARG% > "%FLAG_FILE%"
echo      Flag file created at: %FLAG_FILE%
echo.

echo [2/3] Starting test suite on the current OS...
echo      This will now be handled by run_automation.bat
:: Use "call" to ensure control returns to this script when the other finishes.
:: %~dp0 ensures we find the script in the same directory as this one.
call "%~dp0run_automation.bat" %CHIPSET_ARG%
echo.
echo      Current OS tests are complete.
echo.

echo [3/3] Rebooting to the next operating system to continue...
echo      The system will now restart.
powershell.exe -ExecutionPolicy Bypass -File "%REBOOT_SCRIPT%"

echo.
echo Reboot initiated.
goto :eof