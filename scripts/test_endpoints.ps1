# Test job-search-api endpoints. Usage: .\test_endpoints.ps1 [BASE_URL]
param([string]$BaseUrl = "http://localhost:8000")
$BaseUrl = $BaseUrl.TrimEnd("/")
Write-Host "Testing API at $BaseUrl"

Write-Host "`n1. GET /health"
try { (Invoke-RestMethod "$BaseUrl/health") | ConvertTo-Json -Compress } catch { Write-Host "FAIL: $_" }

Write-Host "`n2. GET /debug"
try { $r = Invoke-RestMethod "$BaseUrl/debug"; Write-Host "total_jobs: $($r.total_jobs)"; $r.scrapers.GetEnumerator() | ForEach-Object { Write-Host "  $($_.Key): $($_.Value.count)" } } catch { Write-Host "FAIL: $_" }

Write-Host "`n3. GET /debug/headless (may take ~90s)"
try { $r = Invoke-RestMethod "$BaseUrl/debug/headless" -TimeoutSec 120; if ($r.scrapers) { $r.scrapers.GetEnumerator() | ForEach-Object { Write-Host "  $($_.Key): $($_.Value.count)" } } else { Write-Host $r } } catch { Write-Host "FAIL: $_" }

Write-Host "`n4. POST /refresh?days=3&headless=0"
try { $r = Invoke-RestMethod "$BaseUrl/refresh?days=3&headless=0" -Method Post -TimeoutSec 120; Write-Host "count: $($r.count)" } catch { Write-Host "FAIL: $_" }

Write-Host "`n5. GET /jobs?limit=5"
try { $r = Invoke-RestMethod "$BaseUrl/jobs?limit=5"; Write-Host "count: $($r.count)" } catch { Write-Host "FAIL: $_" }
Write-Host "`nDone."
