# Local Setup Script for Job Search API
# Run this to set up the local development environment

Write-Host "🚀 Setting up Job Search API locally..." -ForegroundColor Cyan
Write-Host ""

# Check Python
Write-Host "1. Checking Python installation..." -ForegroundColor Yellow
try {
    $pythonVersion = python --version 2>&1
    Write-Host "   ✅ $pythonVersion" -ForegroundColor Green
} catch {
    Write-Host "   ❌ Python not found! Please install Python 3.9+" -ForegroundColor Red
    exit 1
}

# Create virtual environment
Write-Host "`n2. Creating virtual environment..." -ForegroundColor Yellow
if (Test-Path .venv) {
    Write-Host "   ⚠️  Virtual environment already exists, skipping..." -ForegroundColor Yellow
} else {
    python -m venv .venv
    Write-Host "   ✅ Virtual environment created" -ForegroundColor Green
}

# Activate virtual environment
Write-Host "`n3. Activating virtual environment..." -ForegroundColor Yellow
& .venv\Scripts\Activate.ps1
Write-Host "   ✅ Virtual environment activated" -ForegroundColor Green

# Upgrade pip
Write-Host "`n4. Upgrading pip..." -ForegroundColor Yellow
python -m pip install --upgrade pip
Write-Host "   ✅ pip upgraded" -ForegroundColor Green

# Install dependencies
Write-Host "`n5. Installing Python dependencies..." -ForegroundColor Yellow
pip install -r requirements.txt
Write-Host "   ✅ Dependencies installed" -ForegroundColor Green

# Install Playwright browser
Write-Host "`n6. Installing Playwright Chromium (required for headless scrapers)..." -ForegroundColor Yellow
Write-Host "   ⏳ This may take a few minutes (~300MB download)..." -ForegroundColor Gray
python -m playwright install chromium
Write-Host "   ✅ Playwright Chromium installed" -ForegroundColor Green

# Create data directory
Write-Host "`n7. Creating data directory..." -ForegroundColor Yellow
if (-not (Test-Path data)) {
    New-Item -ItemType Directory -Path data | Out-Null
    Write-Host "   ✅ Data directory created" -ForegroundColor Green
} else {
    Write-Host "   ⚠️  Data directory already exists" -ForegroundColor Yellow
}

Write-Host "`n✅ Setup complete!`n" -ForegroundColor Green
Write-Host "Next steps:" -ForegroundColor Cyan
Write-Host "  1. Start the server:" -ForegroundColor White
Write-Host "     uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload" -ForegroundColor Gray
Write-Host "`n  2. Test the API:" -ForegroundColor White
Write-Host "     .\test_local.ps1" -ForegroundColor Gray
Write-Host "`n  3. Or test manually:" -ForegroundColor White
Write-Host "     Invoke-RestMethod -Uri 'http://localhost:8000/health'" -ForegroundColor Gray
Write-Host ""
