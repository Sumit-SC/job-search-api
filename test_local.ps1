# Local API Testing Script
# Tests all endpoints locally

param(
    [string]$BaseUrl = "http://localhost:8000"
)

Write-Host "`n🧪 Testing Job Search API Locally" -ForegroundColor Cyan
Write-Host "Base URL: $BaseUrl`n" -ForegroundColor Gray

# Test 1: Health Check
Write-Host "1. Testing /health..." -ForegroundColor Yellow
try {
    $health = Invoke-RestMethod -Uri "$BaseUrl/health" -ErrorAction Stop
    Write-Host "   ✅ Health check passed" -ForegroundColor Green
    Write-Host "   Response: $($health | ConvertTo-Json -Compress)" -ForegroundColor Gray
} catch {
    Write-Host "   ❌ Health check failed: $_" -ForegroundColor Red
    exit 1
}

# Test 2: System Resources
Write-Host "`n2. Testing /system..." -ForegroundColor Yellow
try {
    $system = Invoke-RestMethod -Uri "$BaseUrl/system" -ErrorAction Stop
    Write-Host "   ✅ System endpoint working" -ForegroundColor Green
    Write-Host "   CPU: $($system.cpu.percent)% | Memory: $($system.memory.percent)% | Disk: $($system.disk.percent)%" -ForegroundColor Gray
} catch {
    Write-Host "   ⚠️  System endpoint failed (optional): $_" -ForegroundColor Yellow
}

# Test 3: RSS Scrapers Debug
Write-Host "`n3. Testing /debug (RSS scrapers)..." -ForegroundColor Yellow
try {
    $debug = Invoke-RestMethod -Uri "$BaseUrl/debug" -TimeoutSec 90 -ErrorAction Stop
    Write-Host "   ✅ RSS scrapers working" -ForegroundColor Green
    Write-Host "   Total jobs found: $($debug.total_jobs)" -ForegroundColor Cyan
    if ($debug.scrapers) {
        $scraperCount = if ($debug.scrapers -is [hashtable] -or $debug.scrapers -is [System.Collections.IDictionary]) {
            $debug.scrapers.Count
        } else {
            ($debug.scrapers.PSObject.Properties | Measure-Object).Count
        }
        Write-Host "   Scrapers tested: $scraperCount" -ForegroundColor Gray
        Write-Host "   Top sources:" -ForegroundColor Gray
        $scrapersList = @()
        if ($debug.scrapers -is [hashtable] -or $debug.scrapers -is [System.Collections.IDictionary]) {
            $scrapersList = $debug.scrapers.GetEnumerator() | ForEach-Object { [PSCustomObject]@{ Key = $_.Key; Value = $_.Value } }
        } else {
            $scrapersList = $debug.scrapers.PSObject.Properties | ForEach-Object { [PSCustomObject]@{ Key = $_.Name; Value = $_.Value } }
        }
        $scrapersList | Sort-Object -Property { $_.Value.count } -Descending | Select-Object -First 5 | ForEach-Object {
            Write-Host "     - $($_.Key): $($_.Value.count) jobs" -ForegroundColor Gray
        }
    }
} catch {
    Write-Host "   ❌ RSS debug failed: $_" -ForegroundColor Red
}

# Test 4: Refresh (RSS Only - Fast)
Write-Host "`n4. Testing /refresh (RSS only, fast)..." -ForegroundColor Yellow
try {
    $refresh = Invoke-RestMethod -Uri "$BaseUrl/refresh?q=data%20analyst&days=3&headless=0" -Method Post -TimeoutSec 120 -ErrorAction Stop
    Write-Host "   ✅ Refresh successful" -ForegroundColor Green
    Write-Host "   Jobs scraped: $($refresh.count)" -ForegroundColor Cyan
    if ($refresh.jobs -and $refresh.jobs.Count -gt 0) {
        Write-Host "   Sample job: $($refresh.jobs[0].title) at $($refresh.jobs[0].company)" -ForegroundColor Gray
    }
} catch {
    Write-Host "   ❌ Refresh failed: $_" -ForegroundColor Red
}

# Test 5: Get Jobs
Write-Host "`n5. Testing /jobs..." -ForegroundColor Yellow
try {
    $jobs = Invoke-RestMethod -Uri "$BaseUrl/jobs?limit=10" -ErrorAction Stop
    Write-Host "   ✅ Jobs endpoint working" -ForegroundColor Green
    Write-Host "   Jobs returned: $($jobs.count)" -ForegroundColor Cyan
    if ($jobs.jobs -and $jobs.jobs.Count -gt 0) {
        Write-Host "   Sample job: $($jobs.jobs[0].title) at $($jobs.jobs[0].company)" -ForegroundColor Gray
    }
} catch {
    Write-Host "   ❌ Jobs endpoint failed: $_" -ForegroundColor Red
    Write-Host "   Error details: $($_.Exception.Message)" -ForegroundColor Red
}

# Test 6: Headless Scrapers (Optional, Slow)
Write-Host "`n6. Testing /debug/headless (optional, slow - 2-5 min)..." -ForegroundColor Yellow
$testHeadless = Read-Host "   Test headless scrapers? (y/n)"
if ($testHeadless -eq 'y' -or $testHeadless -eq 'Y') {
    try {
        Write-Host "   ⏳ This will take 2-5 minutes..." -ForegroundColor Yellow
        $headless = Invoke-RestMethod -Uri "$BaseUrl/debug/headless" -TimeoutSec 300 -ErrorAction Stop
        Write-Host "   ✅ Headless scrapers tested" -ForegroundColor Green
        Write-Host "   Total jobs: $($headless.total_jobs)" -ForegroundColor Cyan
        if ($headless.scrapers) {
            Write-Host "   Scraper results:" -ForegroundColor Gray
            $scrapersList = @()
            if ($headless.scrapers -is [hashtable] -or $headless.scrapers -is [System.Collections.IDictionary]) {
                $scrapersList = $headless.scrapers.GetEnumerator() | ForEach-Object { [PSCustomObject]@{ Key = $_.Key; Value = $_.Value } }
            } else {
                $scrapersList = $headless.scrapers.PSObject.Properties | ForEach-Object { [PSCustomObject]@{ Key = $_.Name; Value = $_.Value } }
            }
            $scrapersList | ForEach-Object {
                $status = if ($_.Value.ok) { "✅" } else { "❌" }
                Write-Host "     $status $($_.Key): $($_.Value.count) jobs" -ForegroundColor $(if ($_.Value.ok) { "Green" } else { "Red" })
                if ($_.Value.error) {
                    Write-Host "       Error: $($_.Value.error)" -ForegroundColor Red
                }
            }
        }
    } catch {
        Write-Host "   ❌ Headless debug failed: $_" -ForegroundColor Red
    }
} else {
    Write-Host "   ⏭️  Skipped" -ForegroundColor Gray
}

Write-Host "`n✅ Local testing complete!`n" -ForegroundColor Green
Write-Host "Next steps:" -ForegroundColor Cyan
Write-Host "  - Check server logs for detailed information" -ForegroundColor Gray
Write-Host "  - Test with frontend: Update jobs.html JOB_PROXY_URL to http://localhost:8000" -ForegroundColor Gray
Write-Host "  - Test headless scrapers individually if needed" -ForegroundColor Gray
