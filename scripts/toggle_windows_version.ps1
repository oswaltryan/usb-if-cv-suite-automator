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

# ---------- 2. pick the other OS ---------------------------
switch -Regex ($currentDesc) {
    'Windows\s*10' { $targetRegex = 'Windows\s*11' }
    'Windows\s*11' { $targetRegex = 'Windows\s*10' }
    default {
        Write-Error "Can't decide which OS to toggle to (description = '$currentDesc')."
        exit 1
    }
}

# ---------- 3. locate that loader’s GUID -------------------
$bcdLines   = & bcdedit /enum all /v
[string]$targetGuid = $null

for ($i = 0; $i -lt $bcdLines.Count; $i++) {
    if ($bcdLines[$i] -match '^\s*identifier\s+\{([0-9a-fA-F\-]+)\}') {
        $guid = '{' + $Matches[1] + '}'
    }
    if ($bcdLines[$i] -match "^\s*description\s+$targetRegex") {
        $targetGuid = $guid
        break
    }
}

if (-not $targetGuid) {
    Write-Error "Couldn't find a loader whose description matches '$targetRegex'."
    exit 1
}

# ---------- 4. queue it for the very next boot -------------
Write-Host "Current OS   : $currentDesc  ($currentGuid)"
Write-Host "Next boot --> : $targetRegex ($targetGuid)"
& bcdedit /bootsequence "$targetGuid"
& shutdown /r /t 0
