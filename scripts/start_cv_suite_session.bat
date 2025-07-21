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
echo [1/4] Creating automation "baton" for the next OS...
echo %CHIPSET_ARG% > "%FLAG_FILE%"
echo      Flag file created at: %FLAG_FILE%
echo.

echo [2/4] Starting test suite on the current OS...
echo      This will now be handled by run_automation.bat
call "%~dp0run_automation.bat" %CHIPSET_ARG%
echo.

:: vvvvvvvvvvvvvvv THE FIX IS HERE vvvvvvvvvvvvvvvvvvv
:: Check the exit code (%ERRORLEVEL%) of the last command (run_automation.bat).
:: By quoting the variables, we prevent syntax errors if %ERRORLEVEL% is empty.
echo [3/4] Checking for automation script errors...
if "%ERRORLEVEL%" neq "0" (
    echo.
    echo      !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
    echo      !! ERROR: The Python automation script failed with a non-zero    !!
    echo      !!        exit code (%ERRORLEVEL%).                                     !!
    echo      !!                                                               !!
    echo      !!        Aborting the test session. The reboot will be          !!
    echo      !!        cancelled and the flag file will be cleaned up.        !!
    echo      !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
    echo.
    echo      Cleaning up flag file...
    del "%FLAG_FILE%"
    pause
    goto :eof
)
echo      SUCCESS: Script completed without errors.
echo.
:: ^^^^^^^^^^^^^^^^^^^^ THE FIX IS HERE ^^^^^^^^^^^^^^^^^^^^


echo [4/4] Rebooting to the next operating system to continue...
echo      The system will now restart.
powershell.exe -ExecutionPolicy Bypass -File "%REBOOT_SCRIPT%"

echo.
echo Reboot initiated.
goto :eof