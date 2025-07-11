@echo off
:: =========================================================================
:: start_cv_suite_session.bat
:: -------------------------------------------------------------------------
:: Kicks off the full, two-OS test automation.
::
:: Usage:
::   start_cv_suite_session.bat "bridge_controller_chipset"
::
:: Example:
::   start_cv_suite_session.bat "3861EN-FL"
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
set "AUTOMATION_DIR=C:\cv_suite_testing"
set "FLAG_FILE=%AUTOMATION_DIR%\test_in_progress.flag"
set "PYTHON_SCRIPT=%AUTOMATION_DIR%\cv_suite_automation.py"
set "REBOOT_SCRIPT=%AUTOMATION_DIR%\toggle_windows_version.ps1"

echo =================================================
echo  CV Suite Automation - Full Test Initiator
echo =================================================
echo.
echo [1/3] Creating automation "baton" for the next OS...
echo %CHIPSET_ARG% > "%FLAG_FILE%"
echo      Flag file created at: %FLAG_FILE%
echo.

echo [2/3] Starting test suite on the current OS...
echo      This may take a significant amount of time.
python "%PYTHON_SCRIPT%" %CHIPSET_ARG%
echo.
echo      Current OS tests are complete.
echo.

echo [3/3] Rebooting to the next operating system to continue...
echo      The system will now restart.
powershell.exe -ExecutionPolicy Bypass -File "%REBOOT_SCRIPT%"

echo.
echo Reboot initiated.
goto :eof