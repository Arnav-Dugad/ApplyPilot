<#
.SYNOPSIS
  Builds the ApplyPilot Windows app: UI bundle, PyInstaller app folder, portable zip, and installer.
.EXAMPLE
  powershell -ExecutionPolicy Bypass -File packaging\build.ps1
  Outputs land in release\.
#>
param(
  [string]$Version,
  [string]$Python = 'python',
  [switch]$SkipInstaller
)
$ErrorActionPreference = 'Stop'
$Root = Split-Path $PSScriptRoot -Parent
Set-Location $Root

function Invoke-Step([string]$Name, [scriptblock]$Command) {
  Write-Host "==> $Name" -ForegroundColor Cyan
  & $Command
  if ($LASTEXITCODE) { throw "$Name failed with exit code $LASTEXITCODE" }
}

$packageVersion = (Get-Content package.json -Raw | ConvertFrom-Json).version
$backendVersion = (Select-String -Path backend\__init__.py -Pattern '__version__ = "(.+)"').Matches[0].Groups[1].Value
if (-not $Version) { $Version = $packageVersion }
if ($packageVersion -ne $Version -or $backendVersion -ne $Version) {
  throw "Version mismatch: building $Version, package.json has $packageVersion, backend/__init__.py has $backendVersion"
}

Invoke-Step 'Install UI dependencies' { npm ci --no-audit --no-fund }
Invoke-Step 'Build UI' { npm run build }

$venv = Join-Path $Root '.venv-build'
if (-not (Test-Path "$venv\Scripts\python.exe")) { Invoke-Step 'Create build environment' { & $Python -m venv $venv } }
$py = "$venv\Scripts\python.exe"
Invoke-Step 'Install packaging dependencies' { & $py -m pip install --disable-pip-version-check -q -r packaging\requirements-desktop.txt }
Invoke-Step 'Run backend tests' { & $py -m unittest discover -s backend/tests }
Invoke-Step 'Bundle app' { & $py -m PyInstaller packaging\ApplyPilot.spec --noconfirm --clean --distpath build\pyinstaller\dist --workpath build\pyinstaller\work }

New-Item -ItemType Directory -Force release | Out-Null
$zip = "release\ApplyPilot-$Version-portable-win64.zip"
if (Test-Path $zip) { Remove-Item $zip }
# Python's zipfile reads with shared access; Compress-Archive fails while antivirus scans the fresh bundle.
Invoke-Step 'Create portable zip' { Push-Location build\pyinstaller\dist; try { & $py -m zipfile -c "$Root\$zip" ApplyPilot } finally { Pop-Location } }

if (-not $SkipInstaller) {
  $iscc = @(
    (Get-Command iscc.exe -ErrorAction SilentlyContinue).Source,
    "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe",
    "$env:ProgramFiles\Inno Setup 6\ISCC.exe",
    "$env:LOCALAPPDATA\Programs\Inno Setup 6\ISCC.exe"
  ) | Where-Object { $_ -and (Test-Path $_) } | Select-Object -First 1
  if (-not $iscc) { throw 'Inno Setup 6 was not found. Install it (winget install JRSoftware.InnoSetup) or pass -SkipInstaller.' }
  Invoke-Step 'Build installer' { & $iscc /Qp "/DAppVersion=$Version" packaging\installer.iss }
}

Get-ChildItem release | Where-Object Name -like "*$Version*" | ForEach-Object { '{0,-45} {1,8:N1} MB' -f $_.Name, ($_.Length / 1MB) }
