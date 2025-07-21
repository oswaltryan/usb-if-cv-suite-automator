@echo off
:: =========================================================================
:: run_automation.bat
:: -------------------------------------------------------------------------
:: The main entry point for a single-OS test.
:: This version correctly sets the PYTHONPATH and returns the Python
:: script's exit code. It does NOT use a virtual environment.
:: =========================================================================

:: Get the directory of the project root (one level up from this script)
for %%I in ("%~dp0\..") do set "PROJECT_ROOT=%%~fI"
set "SRC_PATH=%PROJECT_ROOT%\src"

:: --- Set PYTHONPATH to find our source code ---
set "ORIGINAL_PYTHONPATH=%PYTHONPATH%"
set "PYTHONPATH=%SRC_PATH%;%PYTHONPATH%"

echo --- Starting CV Suite Automator ---
:: Run the Python package as a module, forwarding all arguments (%*)
python -m cv_suite_automator %*

:: --- Capture the Python script's exit code ---
set "PY_EXIT_CODE=%ERRORLEVEL%"

:: --- Restore original PYTHONPATH ---
set "PYTHONPATH=%ORIGINAL_PYTHONPATH%"
set "ORIGINAL_PYTHONPATH="

echo --- Automation finished. ---

:: --- Exit with the captured exit code ---
exit /b %PY_EXIT_CODE%