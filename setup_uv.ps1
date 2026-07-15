Param(
  [switch]$InstallPlaywright,
  [switch]$StartApi,
  [switch]$RunAudit,
  [switch]$OpenNotebook
)

$ErrorActionPreference = "Stop"

Write-Host "== Job Search API uv setup ==" -ForegroundColor Cyan

function Has-Command($name) {
  return [bool](Get-Command $name -ErrorAction SilentlyContinue)
}

if (-not (Has-Command "uv")) {
  Write-Host "uv not found. Installing uv..." -ForegroundColor Yellow
  powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
  $env:Path = "$HOME\.cargo\bin;$env:Path"
}

if (-not (Test-Path ".venv")) {
  Write-Host "Creating .venv with uv..." -ForegroundColor Yellow
  uv venv --python 3.11
}

Write-Host "Installing Python dependencies..." -ForegroundColor Yellow
uv pip install -r requirements.txt
uv pip install notebook

if ($InstallPlaywright) {
  Write-Host "Installing Playwright Chromium..." -ForegroundColor Yellow
  uv run playwright install chromium
}

if ($RunAudit) {
  Write-Host "Running audit script..." -ForegroundColor Yellow
  uv run python scripts/job_api_audit.py
}

if ($OpenNotebook) {
  Write-Host "Starting Jupyter Notebook..." -ForegroundColor Yellow
  uv run jupyter notebook
  exit 0
}

if ($StartApi) {
  Write-Host "Starting API server..." -ForegroundColor Green
  uv run uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
  exit 0
}

Write-Host "Setup complete." -ForegroundColor Green
Write-Host "Next commands:" -ForegroundColor Cyan
Write-Host "  .\setup_uv.ps1 -InstallPlaywright -RunAudit"
Write-Host "  .\setup_uv.ps1 -StartApi"
Write-Host "  .\setup_uv.ps1 -OpenNotebook"
