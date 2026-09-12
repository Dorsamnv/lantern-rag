# Start Lantern UI (port 5173)
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot\frontend

if (-not (Test-Path .\node_modules)) {
  npm install
}

Write-Host "Lantern UI → http://127.0.0.1:5173"
npm run dev
