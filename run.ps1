# One-command Windows launcher for MPLADS Sentinel.
# Run from PowerShell: .\run.ps1

$ErrorActionPreference = "Stop"
$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$backendDir = Join-Path $projectRoot "backend"
Set-Location $backendDir

if (-not (Test-Path "venv\Scripts\python.exe")) {
    Write-Host "Creating Python virtual environment..."
    py -3 -m venv venv
}

& .\venv\Scripts\python.exe -m pip install -q -r requirements.txt

Write-Host "Importing the bundled MPLADS allocation dataset..."
& .\venv\Scripts\python.exe data_loader.py

Write-Host "Training the unsupervised allocation-pattern model..."
& .\venv\Scripts\python.exe -m ml.train

Write-Host "Starting MPLADS Sentinel at http://localhost:5000"
& .\venv\Scripts\python.exe app.py
