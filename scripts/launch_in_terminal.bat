@echo off
:: =========================================================================
:: launch_in_terminal.bat (Timing-Fix Version)
:: -------------------------------------------------------------------------
:: This script addresses a race condition where the agent might launch
:: before the Windows Terminal service is ready during user logon.
::
:: It introduces a 5-second delay to ensure the desktop environment is
:: stable, then launches the agent in Windows Terminal.
:: =========================================================================

:: Wait for 5 seconds to allow the system to settle.
:: The > nul hides the countdown message.
timeout /t 5 /nobreak > nul

:: Now, launch the command prompt inside Windows Terminal.
:: The /k switch is critical to KEEP the window open for interaction.
wt.exe cmd.exe /k "%~dp0autostart_cv_suite_testing.bat"