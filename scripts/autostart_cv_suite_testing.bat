@echo off
:: =========================================================================
:: autostart_cv_suite_testing.bat
:: -------------------------------------------------------------------------
:: This script runs at Windows startup.
:: It checks for a flag file to continue a test session initiated
:: on the other operating system.
:: =========================================================================

set "AUTOMATION_DIR=C:\cv_suite_testing"
set "FLAG_FILE=%AUTOMATION_DIR%\test_in_progress.flag"
set "PYTHON_SCRIPT=%AUTOMATION_DIR%\cv_suite_automation.py"

:: --- 1. Check if we need to do anything ---
if not exist "%FLAG_FILE%" (
    :: No flag file found. This means no test is in progress. Exit silently.
    goto :eof
)

echo =================================================
echo  CV Suite Automation - Continuation Agent
echo =================================================
echo.
echo [1/3] "Baton" file found. A test session is in progress.
echo.

echo [2/3] Reading chipset argument and starting test suite...
set /p CHIPSET_ARG=<"%FLAG_FILE%"
python "%PYTHON_SCRIPT%" %CHIPSET_ARG%
echo.
echo      Test suite for this OS is now complete.
echo.

echo [3/3] Automation session is finished. Cleaning up...
del "%FLAG_FILE%"
echo      Flag file has been deleted.
echo.

echo =================================================
echo  Test Session Complete. System is now idle.
echo =================================================

:: Pause for 15 seconds so the operator can see the completion message
timeout /t 15 > nul