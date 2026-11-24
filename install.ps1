# Install Skywall for the current Windows user: venv, scheduled task, Start-menu entries
# (Ctrl+Alt+S opens Stellarium), and a desktop right-click entry.
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot
if (-not (Test-Path .venv)) { py -3 -m venv .venv }
.\.venv\Scripts\python.exe -m pip install -q -e .
.\.venv\Scripts\python.exe -m pip install -q pycairo
.\.venv\Scripts\python.exe -m skywall.cli install
Write-Host "Installed. Run '.venv\Scripts\skywall settings' to set your location and facing, then '.venv\Scripts\skywall enable'."
