@echo off
:: =========================================================================
:: task_scheduler_launcher.bat (Definitive -d Switch Version)
:: -------------------------------------------------------------------------
:: This is the final, correct launcher. It uses the built-in and reliable
:: "-d" (directory) switch of wt.exe to solve the working directory problem.
::
:: 1. It determines the project root and the path to the PowerShell agent.
:: 2. It launches wt.exe, explicitly telling it:
::    - What directory to start in (-d).
::    - To run PowerShell and keep it open (-NoExit).
::    - What PowerShell script file to run (-File).
:: =========================================================================

:: 1. Define the absolute paths to the project root and the agent script.
for %%I in ("%~dp0\..") do set "PROJECT_ROOT=%%~fI"
set "PS_AGENT_SCRIPT=%PROJECT_ROOT%\scripts\autostart.ps1"

:: 2. Launch Windows Terminal with the correct directory and script.
wt.exe -d "%PROJECT_ROOT%" powershell.exe -NoExit -File "%PS_AGENT_SCRIPT%"