@echo off
:: =========================================================================
:: start_cv_suite_session.bat
:: -------------------------------------------------------------------------
:: Kicks off the full, two-OS test automation.
:: This version includes robust error handling to abort on script failure.
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
for %%I in ("%~dp0\..") do set "PROJECT_ROOT=%%~fI"
set "FLAG_FILE=%PROJECT_ROOT%\test_in_progress.flag"
set "REBOOT_SCRIPT=%~dp0toggle_windows_version.ps1"

echo =================================================
echo  CV Suite Automation - Full Session Initiator
echo =================================================
echo.
echo [1/3] Creating automation "baton" for the next OS...
echo %CHIPSET_ARG% > "%FLAG_FILE%"
echo.

echo [2/3] Starting test suite on the current OS...
call "%~dp0run_automation.bat" %CHIPSET_ARG%
echo.

:: --- Check for automation script errors ---
echo [3/3] Checking for script errors...

:: vvvvvvvvvvvvvvv THE FIX IS HERE vvvvvvvvvvvvvvvvvvv
:: This uses a much simpler, more robust error message block.
:: It also still uses the safe, quoted comparison.
if "%ERRORLEVEL%" neq "0" (
    echo.
    echo ERROR: The Python automation script failed with exit code %ERRORLEVEL%.
    echo Aborting the test session and cleaning up the flag file.
    echo The system will NOT be rebooted.
    echo.
    del "%FLAG_FILE%"
    pause
    goto :eof
)
:: ^^^^^^^^^^^^^^^^^^^^ THE FIX IS HERE ^^^^^^^^^^^^^^^^^^^^

echo      SUCCESS: Script completed without errors.
echo.

@REM echo [4/4] Rebooting to the next operating system to continue...
@REM powershell.exe -ExecutionPolicy Bypass -File "%REBOOT_SCRIPT%"
@REM goto :eof