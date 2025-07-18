@echo off
:: =========================================================================
:: autostart_cv_suite_testing.bat
:: -------------------------------------------------------------------------
:: Runs at startup to continue a test session.
:: =========================================================================
for %%I in ("%~dp0\..") do set "PROJECT_ROOT=%%~fI"
set "FLAG_FILE=%PROJECT_ROOT%\test_in_progress.flag"
set "RUNNER_SCRIPT=%~dp0run_automation.bat"

if not exist "%FLAG_FILE%" (
    goto :eof
)

echo [1/3] "Baton" file found. Continuing test session...
set /p CHIPSET_ARG=<"%FLAG_FILE%"

echo [2/3] Starting test suite...
call "%RUNNER_SCRIPT%" %CHIPSET_ARG%

echo [3/3] Automation session finished. Cleaning up...
del "%FLAG_FILE%"
timeout /t 15 > nul