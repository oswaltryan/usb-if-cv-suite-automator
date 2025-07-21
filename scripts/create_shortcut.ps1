<#
.SYNOPSIS
    Creates a .lnk shortcut file. Designed to be called from a batch script.
#>
param(
    [Parameter(Mandatory=$true)]
    [string]$ShortcutPath,

    [Parameter(Mandatory=$true)]
    [string]$TargetPath,

    [Parameter(Mandatory=$true)]
    [string]$WorkingDirectory
)

try {
    $ws = New-Object -ComObject WScript.Shell
    $s = $ws.CreateShortcut($ShortcutPath)
    $s.TargetPath = $TargetPath
    $s.WorkingDirectory = $WorkingDirectory
    $s.Description = 'Starts the CV Suite automation agent in Windows Terminal.'
    $s.Save()
    exit 0
}
catch {
    # If any error occurs, write it to the error stream and exit with code 1
    Write-Error "PowerShell Error: Failed to create shortcut. Reason: $($_.Exception.Message)"
    exit 1
}