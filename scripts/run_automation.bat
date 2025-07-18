@echo off
:: =========================================================================
:: run_automation.bat
:: -------------------------------------------------------------------------
:: The main entry point for running a manual test.
:: This script correctly sets the PYTHONPATH before executing the
:: Python application from the global Python installation.
::
:: All arguments passed to this script will be forwarded to the Python app.
:: =========================================================================

:: Get the directory of the project root (one level up from this script)
for %%I in ("%~dp0\..") do set "PROJECT_ROOT=%%~fI"
set "SRC_PATH=%PROJECT_ROOT%\src"

:: --- Set PYTHONPATH to find our source code ---
:: Temporarily add the 'src' directory to the PYTHONPATH.
:: This tells Python where to find our 'cv_suite_automator' package.
set "ORIGINAL_PYTHONPATH=%PYTHONPATH%"
set "PYTHONPATH=%SRC_PATH%;%PYTHONPATH%"

echo --- Starting CV Suite Automator ---
:: Run the Python package as a module, forwarding all arguments (%*)
python -m cv_suite_automator %*

:: --- Restore original PYTHONPATH ---
set "PYTHONPATH=%ORIGINAL_PYTHONPATH%"
set "ORIGINAL_PYTHONPATH="

echo.
echo --- Automation finished. ---
pause