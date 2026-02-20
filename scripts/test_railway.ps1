# PowerShell test script for Railway deployment
# Usage: .\test_railway.ps1 https://your-app.up.railway.app

param(
    [string]$BaseUrl = "http://localhost:8000"
)

Write-Host "Testing Railway deployment at: $BaseUrl" -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host ""

# Test health endpoint
Write-Host "1. Testing /health..." -ForegroundColor Yellow
try {
    $health = Invoke-RestMethod -Uri "$BaseUrl/health" -Method Get -ErrorAction Stop
    if ($health.ok) {
        Write-Host "✅ Health check passed" -ForegroundColor Green
    } else {
        Write-Host "❌ Health check failed" -ForegroundColor Red
        exit 1
    }
} catch {
    Write-Host "❌ Health check failed: $_" -ForegroundColor Red
    exit 1
}
Write-Host ""

# Test system endpoint
Write-Host "2. Testing /system..." -ForegroundColor Yellow
try {
    $system = Invoke-RestMethod -Uri "$BaseUrl/system" -Method Get -ErrorAction Stop
    if ($system.ok) {
        Write-Host "✅ System endpoint working" -ForegroundColor Green
        Write-Host ($system | ConvertTo-Json -Depth 3)
    } else {
        Write-Host "⚠️  System endpoint returned non-ok status" -ForegroundColor Yellow
    }
} catch {
    Write-Host "⚠️  System endpoint error: $_" -ForegroundColor Yellow
}
Write-Host ""

# Test debug RSS scrapers
Write-Host "3. Testing /debug (RSS scrapers)..." -ForegroundColor Yellow
try {
    $debug = Invoke-RestMethod -Uri "$BaseUrl/debug" -Method Get -ErrorAction Stop
    if ($debug.ok) {
        Write-Host "✅ RSS scrapers test passed" -ForegroundColor Green
        $scraperCount = ($debug.scrapers | Measure-Object).Count
        Write-Host "   Found $scraperCount scrapers"
    } else {
        Write-Host "⚠️  Debug endpoint issue" -ForegroundColor Yellow
    }
} catch {
    Write-Host "⚠️  Debug endpoint error: $_" -ForegroundColor Yellow
}
Write-Host ""

# Test refresh endpoint (RSS only, fast)
Write-Host "4. Testing /refresh?headless=0 (RSS only)..." -ForegroundColor Yellow
try {
    $refresh = Invoke-RestMethod -Uri "$BaseUrl/refresh?q=data%20analyst&days=3&headless=0" -Method Post -ErrorAction Stop
    if ($refresh.ok) {
        Write-Host "✅ Refresh endpoint working (RSS only)" -ForegroundColor Green
        $jobCount = ($refresh.jobs | Measure-Object).Count
        Write-Host "   Scraped $jobCount jobs"
    } else {
        Write-Host "⚠️  Refresh endpoint issue" -ForegroundColor Yellow
    }
} catch {
    Write-Host "⚠️  Refresh endpoint error: $_" -ForegroundColor Yellow
}
Write-Host ""

# Test jobs endpoint
Write-Host "5. Testing /jobs..." -ForegroundColor Yellow
try {
    $jobs = Invoke-RestMethod -Uri "$BaseUrl/jobs?limit=10" -Method Get -ErrorAction Stop
    if ($jobs.ok) {
        Write-Host "✅ Jobs endpoint working" -ForegroundColor Green
        $jobCount = ($jobs.jobs | Measure-Object).Count
        Write-Host "   Retrieved $jobCount jobs"
    } else {
        Write-Host "⚠️  Jobs endpoint issue" -ForegroundColor Yellow
    }
} catch {
    Write-Host "⚠️  Jobs endpoint error: $_" -ForegroundColor Yellow
}
Write-Host ""

Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "✅ All basic tests completed!" -ForegroundColor Green
Write-Host ""
Write-Host "To test headless scrapers (slower):" -ForegroundColor Cyan
Write-Host "  Invoke-RestMethod -Uri '$BaseUrl/refresh?q=data%20analyst&days=3' -Method Post"
Write-Host ""
Write-Host "To test headless debug endpoint:" -ForegroundColor Cyan
Write-Host "  Invoke-RestMethod -Uri '$BaseUrl/debug/headless' -Method Get"
