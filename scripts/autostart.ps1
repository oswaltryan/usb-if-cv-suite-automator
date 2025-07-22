# =========================================================================
# autostart.ps1
# -------------------------------------------------------------------------
# This version incorporates the user's correct, working argument list.
# It correctly runs the Python package and waits for interactive input.
# =========================================================================
Set-StrictMode -Version Latest

try {
    # Define paths relative to the project root.
    $ProjectRoot = (Get-Item $PSScriptRoot).Parent.FullName
    $FlagFile = Join-Path -Path $ProjectRoot -ChildPath "test_in_progress.flag"

    # 1. Gatekeeper: Exit silently if no test is in progress.
    if (-not (Test-Path -Path $FlagFile)) {
        exit 0
    }

    Write-Host "[1/3] 'Baton' file found. Continuing test session..." -ForegroundColor Green

    # 2. Argument Retriever: Read and trim the chipset name from the flag file.
    $ChipsetArg = (Get-Content -Path $FlagFile -TotalCount 1).Trim()

    Write-Host "[2/3] Starting Python automation..." -ForegroundColor Green
    Write-Host "------------------------------------------------"

    # 3. The Call: Invoke Python using the correct argument list.
    $env:PYTHONPATH = "$ProjectRoot\src;" + $env:PYTHONPATH
    
    $PythonExe = "python.exe"
    
    # The user's correct, working argument list.
    $ArgumentList = @(
        "-m",
        "cv_suite_automator",
        "`"$ChipsetArg`""
    )

    # Execute the command.
    & $PythonExe $ArgumentList

    if ($LASTEXITCODE -ne 0) {
        throw "The Python script failed with exit code $LASTEXITCODE."
    }

    Write-Host "------------------------------------------------"
    Write-Host "[3/3] Automation session finished. Cleaning up..." -ForegroundColor Green

    # 4. Janitor: Delete the flag file.
    Remove-Item -Path $FlagFile -Force -ErrorAction SilentlyContinue

    Write-Host "Success. This window will close in 15 seconds."
    Start-Sleep -Seconds 15
}
catch {
    # If any error occurs, display it and wait for user input.
    Write-Error "A fatal error occurred in the automation agent: $_"
    Read-Host "Press ENTER to close the window"
    exit 1
}