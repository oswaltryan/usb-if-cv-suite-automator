@echo off
:: =========================================================================
:: autostart_cv_suite_testing.bat (Definitive Final Version)
:: -------------------------------------------------------------------------
:: This script's only job is to check for the flag file and then CALL the
:: proven 'run_automation.bat' script to do the actual work.
:: =========================================================================

:: --- Setup Paths and Log File ---
cd /d "%~dp0"
for %%I in ("%~dp0\..") do set "PROJECT_ROOT=%%~fI"
set "FLAG_FILE=%PROJECT_ROOT%\test_in_progress.flag"
set "RUNNER_SCRIPT=%~dp0run_automation.bat"
set "LOG_FILE=%PROJECT_ROOT%\autostart_debug.log"

:: Create or clear the log file
echo =============================================================== > "%LOG_FILE%"
echo Autostart Agent Log - %DATE% %TIME% >> "%LOG_FILE%"
echo =============================================================== >> "%LOG_FILE%"

:: --- Check if we need to do anything ---
if not exist "%FLAG_FILE%" (
    echo [INFO] Flag file not found. Exiting. >> "%LOG_FILE%"
    goto :eof
)

echo [SUCCESS] Flag file found. >> "%LOG_FILE%"

:: --- Read Argument ---
for /f "usebackq delims=" %%a in (`powershell -Command "(Get-Content -Path '%FLAG_FILE%' -Raw).Trim()"`) do set "CHIPSET_ARG=%%a"
echo [INFO] Chipset argument read as: "%CHIPSET_ARG%" >> "%LOG_FILE%"
echo. >> "%LOG_FILE%"

:: vvvvvvvvvvvvvvv THE FIX IS HERE vvvvvvvvvvvvvvvvvvv
:: Instead of calling python directly, we call the script that we KNOW works.
echo [DEBUG] Calling the main runner script (run_automation.bat)... >> "%LOG_FILE%"
echo --------------------------------------------------------------- >> "%LOG_FILE%"

call "%RUNNER_SCRIPT%" "%CHIPSET_ARG%" >> "%LOG_FILE%" 2>&1
set "PY_EXIT_CODE=%ERRORLEVEL%"

echo --------------------------------------------------------------- >> "%LOG_FILE%"
echo [INFO] Runner script finished with exit code: %PY_EXIT_CODE% >> "%LOG_FILE%"
:: ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

:: --- Check for Errors and Clean Up ---
if "%PY_EXIT_CODE%" neq "0" (
    echo [ERROR] The Python script failed. The flag file will NOT be deleted. >> "%LOG_FILE%"
    goto :eof
)

echo [SUCCESS] Python script completed. Deleting flag file. >> "%LOG_FILE%"
del "%FLAG_FILE%"
echo [INFO] Automation session for this OS is complete. >> "%LOG_FILE%"