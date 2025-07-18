@echo off
:: =========================================================================
:: start_cv_suite_session.bat
:: -------------------------------------------------------------------------
:: Kicks off the full, two-OS test automation.
:: =========================================================================

:: --- Validate Input ---
if "%~1"=="" (
    echo ERROR: Missing argument.
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
echo [1/3] Creating automation "baton" for the next OS...
echo %CHIPSET_ARG% > "%FLAG_FILE%"
echo.

echo [2/3] Starting test suite on the current OS...
call "%~dp0run_automation.bat" %CHIPSET_ARG%
echo.

echo [3/3] Rebooting to the next operating system to continue...
powershell.exe -ExecutionPolicy Bypass -File "%REBOOT_SCRIPT%"
goto :eof