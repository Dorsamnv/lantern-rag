# Start Lantern API (port 8000)
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

if (-not (Test-Path .\.venv\Scripts\python.exe)) {
  Write-Host "Creating venv..."
  python -m venv .venv
  .\.venv\Scripts\python -m pip install --upgrade pip
  .\.venv\Scripts\pip install -r backend\requirements.txt
}

if (-not (Test-Path .\.env)) {
  Copy-Item .\.env.example .\.env
  Write-Host "Created .env — add GROQ_API_KEY before chatting."
}

Set-Location backend
Write-Host "Lantern API → http://127.0.0.1:8000/docs"
& "$PSScriptRoot\.venv\Scripts\python.exe" -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
