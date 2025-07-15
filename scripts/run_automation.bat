@echo off
:: =========================================================================
:: run_automation.bat
:: -------------------------------------------------------------------------
:: The main entry point for running a manual test.
:: This script automatically activates the virtual environment before
:: executing the Python application.
::
:: All arguments passed to this script will be forwarded to the Python app.
:: =========================================================================

:: Get the directory of the project root (one level up from this script)
set "PROJECT_ROOT=%~dp0.."
set "VENV_PATH=%PROJECT_ROOT%\venv"

:: Check if the virtual environment exists
if not exist "%VENV_PATH%\Scripts\activate.bat" (
    echo ERROR: Virtual environment not found.
    echo Please run the setup steps in the README.md file first.
    echo Expected to find venv at: %VENV_PATH%
    pause
    goto :eof
)

echo --- Activating virtual environment ---
call "%VENV_PATH%\Scripts\activate.bat"

echo --- Starting CV Suite Automator ---
:: Run the Python package as a module, forwarding all arguments (%*)
python -m cv_suite_automator %*

echo --- Automation finished. Deactivating virtual environment. ---
call "%VENV_PATH%\Scripts\deactivate.bat"

echo.
pause