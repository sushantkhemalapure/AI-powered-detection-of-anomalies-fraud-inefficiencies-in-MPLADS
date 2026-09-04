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

if (-not (Test-Path "data\mplads.db")) {
    Write-Host "Generating synthetic MPLADS demonstration data..."
    & .\venv\Scripts\python.exe data_generator.py --works 3200 --anomaly-rate 0.09
}

if (-not (Test-Path "ml\artifacts\isolation_forest.joblib")) {
    Write-Host "Training anomaly-detection model..."
    & .\venv\Scripts\python.exe -m ml.train
}

Write-Host "Starting MPLADS Sentinel at http://localhost:5000"
& .\venv\Scripts\python.exe app.py
