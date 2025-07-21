@echo off
:: (The top part of the script is the same)
:: ...
set "CHIPSET_ARG=%~1"
for %%I in ("%~dp0\..") do set "PROJECT_ROOT=%%~fI"
set "FLAG_FILE=%PROJECT_ROOT%\test_in_progress.flag"
set "REBOOT_SCRIPT=%~dp0toggle_windows_version.ps1"

echo =================================================
echo  CV Suite Automation - Full Session Initiator
echo =================================================
echo.
echo [1/3] Creating automation "baton" for the next OS...
:: vvvvvvvvvvvvvvv THE FIX IS HERE vvvvvvvvvvvvvvvvvvv
:: Use cmd /c to ensure the file is created with standard ANSI encoding, not Unicode
cmd /c "echo %CHIPSET_ARG% > "%FLAG_FILE%""
:: ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
echo.

echo [2/3] Starting test suite on the current OS...
call "%~dp0run_automation.bat" %CHIPSET_ARG%
echo.

:: (The rest of the script is the same)
:: ...
if "%ERRORLEVEL%" neq "0" (
    echo.
    echo ERROR: The Python automation script failed with exit code %ERRORLEVEL%.
    del "%FLAG_FILE%"
    pause
    goto :eof
)
echo      SUCCESS: Script completed without errors.
echo.
echo [4/4] Rebooting to the next operating system to continue...
powershell.exe -ExecutionPolicy Bypass -File "%REBOOT_SCRIPT%"
goto :eof