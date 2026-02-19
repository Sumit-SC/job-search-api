# Test Railway deployment endpoints
# Usage: .\test_railway.ps1 [BASE_URL]
param([string]$BaseUrl = "https://job-search-api-production-5d5d.up.railway.app")
$BaseUrl = $BaseUrl.TrimEnd("/")
Write-Host "Testing Railway API at $BaseUrl" -ForegroundColor Cyan
Write-Host ""

# 1. Health check
Write-Host "1. GET /health" -ForegroundColor Yellow
try {
    $r = Invoke-RestMethod "$BaseUrl/health"
    Write-Host "   ✓ ok: $($r.ok), timestamp: $($r.timestamp)" -ForegroundColor Green
} catch {
    Write-Host "   ✗ FAIL: $_" -ForegroundColor Red
}
Write-Host ""

# 2. Debug RSS scrapers
Write-Host "2. GET /debug (RSS/HTTP scrapers - tests all 11 sources)" -ForegroundColor Yellow
try {
    $r = Invoke-RestMethod "$BaseUrl/debug" -TimeoutSec 60
    Write-Host "   ✓ ok: $($r.ok), total_jobs found: $($r.total_jobs)" -ForegroundColor Green
    Write-Host "   Scraper results:" -ForegroundColor Gray
    foreach ($k in ($r.scrapers.PSObject.Properties.Name | Sort-Object)) {
        $s = $r.scrapers.$k
        $status = if ($s.ok) { "✓" } else { "✗" }
        $color = if ($s.ok) { "Green" } else { "Red" }
        Write-Host "     $status $k : count=$($s.count)" -ForegroundColor $color
        if ($s.error) { Write-Host "       error: $($s.error)" -ForegroundColor Red }
    }
} catch {
    Write-Host "   ✗ FAIL: $_" -ForegroundColor Red
}
Write-Host ""

# 3. Refresh jobs (RSS-only, fast)
Write-Host "3. POST /refresh?days=7&headless=0 (RSS-only scrape and save)" -ForegroundColor Yellow
Write-Host "   This will take 10-30 seconds..." -ForegroundColor Gray
try {
    $r = Invoke-RestMethod "$BaseUrl/refresh?days=7&headless=0" -Method Post -TimeoutSec 120
    Write-Host "   ✓ ok: $($r.ok), jobs scraped and saved: $($r.count)" -ForegroundColor Green
} catch {
    Write-Host "   ✗ FAIL: $_" -ForegroundColor Red
}
Write-Host ""

# 4. Get jobs (should now have data)
Write-Host "4. GET /jobs?days=7&limit=5" -ForegroundColor Yellow
try {
    $r = Invoke-RestMethod "$BaseUrl/jobs?days=7&limit=5"
    Write-Host "   ✓ ok: $($r.ok), jobs returned: $($r.count)" -ForegroundColor Green
    if ($r.jobs.Count -gt 0) {
        Write-Host "   First job:" -ForegroundColor Gray
        $first = $r.jobs[0]
        Write-Host "     Title: $($first.title)" -ForegroundColor White
        Write-Host "     Company: $($first.company)" -ForegroundColor White
        Write-Host "     Source: $($first.source)" -ForegroundColor White
        Write-Host "     Match Score: $($first.match_score)" -ForegroundColor Cyan
        if ($first.yoe_min -or $first.yoe_max) {
            Write-Host "     YOE: $($first.yoe_min)-$($first.yoe_max)" -ForegroundColor Cyan
        }
    }
} catch {
    Write-Host "   ✗ FAIL: $_" -ForegroundColor Red
}
Write-Host ""

# 5. Test sorting by relevance
Write-Host "5. GET /jobs?days=7&limit=3&sort=relevance" -ForegroundColor Yellow
try {
    $r = Invoke-RestMethod "$BaseUrl/jobs?days=7&limit=3&sort=relevance"
    Write-Host "   ✓ ok: $($r.ok), jobs returned: $($r.count)" -ForegroundColor Green
    if ($r.jobs.Count -gt 0) {
        Write-Host "   Top matches (by match_score):" -ForegroundColor Gray
        foreach ($job in $r.jobs) {
            Write-Host "     Score: $($job.match_score) - $($job.title) @ $($job.source)" -ForegroundColor White
        }
    }
} catch {
    Write-Host "   ✗ FAIL: $_" -ForegroundColor Red
}
Write-Host ""

# 6. Test YOE filtering
Write-Host "6. GET /jobs?days=7&limit=3&yoe_min=1&yoe_max=3" -ForegroundColor Yellow
try {
    $r = Invoke-RestMethod "$BaseUrl/jobs?days=7&limit=3&yoe_min=1&yoe_max=3"
    Write-Host "   ✓ ok: $($r.ok), jobs returned: $($r.count)" -ForegroundColor Green
    if ($r.jobs.Count -gt 0) {
        Write-Host "   Jobs matching YOE 1-3:" -ForegroundColor Gray
        foreach ($job in $r.jobs) {
            $yoe = if ($job.yoe_min -or $job.yoe_max) { "$($job.yoe_min)-$($job.yoe_max)" } else { "N/A" }
            Write-Host "     YOE: $yoe - $($job.title)" -ForegroundColor White
        }
    }
} catch {
    Write-Host "   ✗ FAIL: $_" -ForegroundColor Red
}
Write-Host ""

# 7. Test headless scrapers (optional, slow)
Write-Host "7. GET /debug/headless (LinkedIn, Indeed, Naukri - SLOW, ~90s)" -ForegroundColor Yellow
Write-Host "   Skip this? (y/n) - Press Enter to continue or 'y' to skip" -ForegroundColor Gray
$skip = Read-Host
if ($skip -ne "y") {
    try {
        $r = Invoke-RestMethod "$BaseUrl/debug/headless" -TimeoutSec 120
        if ($r.skipped) {
            Write-Host "   ⚠ Skipped: $($r.skipped)" -ForegroundColor Yellow
        } elseif ($r.error) {
            Write-Host "   ✗ Error: $($r.error)" -ForegroundColor Red
        } else {
            Write-Host "   ✓ ok: $($r.ok), total_jobs: $($r.total_jobs)" -ForegroundColor Green
            foreach ($k in ($r.scrapers.PSObject.Properties.Name | Sort-Object)) {
                $s = $r.scrapers.$k
                $status = if ($s.ok) { "✓" } else { "✗" }
                Write-Host "     $status $k : count=$($s.count)" -ForegroundColor $(if ($s.ok) { "Green" } else { "Red" })
            }
        }
    } catch {
        Write-Host "   ✗ FAIL or timeout: $_" -ForegroundColor Red
    }
} else {
    Write-Host "   Skipped." -ForegroundColor Gray
}
Write-Host ""

Write-Host "Done testing Railway API!" -ForegroundColor Cyan
Write-Host "Your API URL: $BaseUrl" -ForegroundColor Cyan
