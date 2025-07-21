@echo off
:: =========================================================================
:: run_automation.bat (Definitive Version)
:: -------------------------------------------------------------------------
:: Executes the Python application by its direct file path, after setting
:: the PYTHONPATH to allow for correct relative imports.
:: =========================================================================

:: Get the directory of the project root (one level up from this script)
for %%I in ("%~dp0\..") do set "PROJECT_ROOT=%%~fI"

:: Define the paths to the 'src' directory and the main script
set "SRC_PATH=%PROJECT_ROOT%\src"
set "MAIN_SCRIPT_PATH=%SRC_PATH%\cv_suite_automator\__main__.py"

:: --- Set PYTHONPATH to find our source code ---
:: This allows the relative 'from .core' import in __main__.py to work.
set "ORIGINAL_PYTHONPATH=%PYTHONPATH%"
set "PYTHONPATH=%SRC_PATH%;%PYTHONPATH%"

echo --- Starting CV Suite Automator ---
:: Run the main Python script directly by its file path, forwarding arguments.
python "%MAIN_SCRIPT_PATH%" %*

:: --- Capture the Python script's exit code ---
set "PY_EXIT_CODE=%ERRORLEVEL%"

:: --- Restore original PYTHONPATH ---
set "PYTHONPATH=%ORIGINAL_PYTHONPATH%"
set "ORIGINAL_PYTHONPATH="

echo --- Automation finished. ---

:: --- Exit with the captured exit code ---
exit /b %PY_EXIT_CODE%