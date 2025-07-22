@echo off
:: =========================================================================
:: start_cv_suite_session.bat
:: -------------------------------------------------------------------------
:: Kicks off the full, two-OS test automation. This is the main entry
:: point for a complete test session.
:: =========================================================================

:: --- 1. Validate Input ---
if "%~1"=="" (
    echo ERROR: Missing argument.
    echo.
    echo Usage: %~n0 "bridge_controller_chipset"
    echo Example: %~n0 "3861EN-FL"
    pause
    goto :eof
)

:: --- 2. Define Paths ---
set "CHIPSET_ARG=%~1"
:: PROJECT_ROOT is defined to find other scripts.
for %%I in ("%~dp0\..") do set "PROJECT_ROOT=%%~fI"
:: Use the M: drive for the flag file for persistence across OSes.
set "FLAG_FILE=M:\test_in_progress.flag"
set "REBOOT_SCRIPT=%~dp0toggle_windows_version.ps1"

echo =================================================
echo  CV Suite Automation - Full Session Initiator
echo =================================================
echo.

:: --- 3. Create Automation Flag File ---
echo [1/3] Creating automation baton for the next OS at: %FLAG_FILE%
:: Use cmd /c to ensure the file is created with standard ANSI encoding.
cmd /c "echo %CHIPSET_ARG% > "%FLAG_FILE%""
if %errorlevel% neq 0 (
    echo ERROR: Could not create flag file at %FLAG_FILE%.
    echo Please ensure the M: drive is available and writable.
    pause
    goto :eof
)
echo.

:: --- 4. Run Tests for the Current OS ---
echo [2/3] Starting test suite on the current OS...
:: Call the proven runner script and pass arguments.
call "%~dp0run_automation.bat" %CHIPSET_ARG%
echo.

:: --- 5. Check for Errors ---
echo [3/3] Checking for script errors...
:: Use robust, quoted comparison for the exit code.
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
echo      SUCCESS: Script completed without errors.
echo.

:: --- 6. Reboot to Next OS ---
echo [4/4] Rebooting to the next operating system to continue...
powershell.exe -ExecutionPolicy Bypass -File "%REBOOT_SCRIPT%"
goto :eof