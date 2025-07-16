<#
  Toggle-Windows.ps1
  ---------------------------------------------------------
  Reboots into the *other* Windows install (10 ↔ 11).
  • No parameters.
  • Uses /bootsequence, so your permanent default is untouched.
#>

# ---------- 1. read the running loader ---------------------
$currentInfo = & bcdedit /enum "{current}" /v

$currentGuid = ($currentInfo |
    Where-Object { $_ -match '^\s*identifier\s+\{' } |
    Select-Object -First 1) -replace '^\s*identifier\s+','' -replace '\s+$',''

$currentDesc = ($currentInfo |
    Where-Object { $_ -match '^\s*description\s+' } |
    Select-Object -First 1) -replace '^\s*description\s+','' -replace '\s+$',''

# ---------- 2. pick the other OS (This section is now more robust) ----
# Use wildcard matching to handle variations like "Pro", "Enterprise", etc.
switch -Wildcard ($currentDesc) {
    '*Windows 10*' { $targetPattern = '*Windows 11*' }
    '*Windows 11*' { $targetPattern = '*Windows 10*' }
    default {
        Write-Error "Can't decide which OS to toggle to (current description = '$currentDesc'). The script only supports toggling between Windows 10 and 11."
        exit 1
    }
}

# ---------- 3. locate that loader’s GUID -------------------
$bcdLines   = & bcdedit /enum all /v
[string]$targetGuid = $null
[string]$targetDesc = $null

for ($i = 0; $i -lt $bcdLines.Count; $i++) {
    if ($bcdLines[$i] -match '^\s*identifier\s+\{([0-9a-fA-F\-]+)\}') {
        $guid = '{' + $Matches[1] + '}'
    }
    # Check if the description line matches our new wildcard pattern
    if ($bcdLines[$i] -match "^\s*description\s+(.*)" -and ($Matches[1] -like $targetPattern)) {
        $targetGuid = $guid
        $targetDesc = $Matches[1].Trim()
        break
    }
}

if (-not $targetGuid) {
    Write-Error "Couldn't find a loader whose description matches the pattern '$targetPattern'."
    exit 1
}

# ---------- 4. queue it for the very next boot -------------
Write-Host "Current OS   : $currentDesc ($currentGuid)"
Write-Host "Next boot --> : $targetDesc ($targetGuid)"
& bcdedit /bootsequence "$targetGuid"
& shutdown /r /t 0