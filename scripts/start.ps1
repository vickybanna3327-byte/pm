$ErrorActionPreference = "Stop"
$rootDir = Split-Path -Parent $PSScriptRoot
Set-Location $rootDir
python -m uvicorn backend.app.main:app --host 0.0.0.0 --port 8000
