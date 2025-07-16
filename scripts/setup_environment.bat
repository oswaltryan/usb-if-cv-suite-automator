@echo off
:: =========================================================================
:: setup_environment.bat
:: -------------------------------------------------------------------------
:: This script creates a clean virtual environment and installs all
:: required packages from the local 'wheels' folder, allowing for a
:: completely offline setup.
::
:: This script only needs to be run once per OS.
:: =========================================================================

:: --- SCRIPT SETUP ---
:: vvvvvvvvvvvvvvvvvvvv THE FIX IS HERE vvvvvvvvvvvvvvvvvvvv
:: This line resolves the relative ".." path into a clean, absolute path
:: that 'pip' will correctly accept.
for %%I in ("%~dp0\..") do set "PROJECT_ROOT=%%~fI"
:: ^^^^^^^^^^^^^^^^^^^^ THE FIX IS HERE ^^^^^^^^^^^^^^^^^^^^

set "VENV_PATH=%PROJECT_ROOT%\venv"
set "WHEELS_PATH=%PROJECT_ROOT%\wheels"
set "REQUIREMENTS_FILE=%PROJECT_ROOT%\requirements.txt"

echo.
echo  CV Suite Automation - Offline Environment Setup
echo  -----------------------------------------------
echo.
pause


:: Step 1: Check for existing virtual environment
if exist "%VENV_PATH%" (
    echo [1/3] Virtual environment already exists. Skipping creation.
) else (
    echo [1/3] Creating virtual environment at: %VENV_PATH%
    python -m venv "%VENV_PATH%"
    if %errorlevel% neq 0 (
        echo      ERROR: Failed to create virtual environment.
        pause
        goto :eof
    )
    echo      SUCCESS: Virtual environment created.
)
echo.


:: Step 2: Activate the virtual environment
echo [2/3] Activating virtual environment for installation...
call "%VENV_PATH%\Scripts\activate.bat"
echo.


:: Step 3: Install packages from local wheels folder
echo [3/3] Installing dependencies from local 'wheels' folder...
echo      This may take a moment.
pip install --no-index --find-links="%WHEELS_PATH%" -r "%REQUIREMENTS_FILE%"

if %errorlevel% neq 0 (
    echo.
    echo      !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
    echo      !! ERROR: Package installation failed.                                !!
    echo      !! Please check that the 'wheels' folder contains all necessary files !!
    echo      !! listed in requirements.txt.                                        !!
    echo      !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
) else (
    echo.
    echo      SUCCESS: All dependencies installed successfully.
)
echo.

:: Deactivate after we are done
call "%VENV_PATH%\Scripts\deactivate.bat"

echo.
echo Environment setup is complete.
pause