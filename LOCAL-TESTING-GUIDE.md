# Local Testing Guide - Job Search API

**Complete guide to test the API locally with headless browsers**

---

## 🎯 Quick Start

You have **two options**:
1. **Direct Python** (No Docker needed) - Faster setup, good for development
2. **Docker** (Optional) - Matches production environment exactly

---

## Option 1: Direct Python (Recommended for Development)

### Prerequisites
- Python 3.9+ installed
- No Docker needed!

### Step 1: Navigate to Project
```powershell
cd w:\CodeBase\Resume-Projects\sumit-personal-site\job-search-api
```

### Step 2: Create Virtual Environment
```powershell
python -m venv .venv
```

### Step 3: Activate Virtual Environment
```powershell
# Windows PowerShell
.venv\Scripts\Activate.ps1

# Windows CMD
.venv\Scripts\activate.bat

# Linux/macOS
source .venv/bin/activate
```

### Step 4: Install Dependencies
```powershell
pip install -r requirements.txt
```

### Step 5: Install Playwright Browser (Required for Headless Scrapers)
```powershell
python -m playwright install chromium
```

**Note:** This downloads Chromium (~300MB). Required for LinkedIn, Indeed, Naukri, etc.

### Step 6: Set Environment Variables (Optional)
```powershell
# Enable headless scrapers (default is enabled)
$env:ENABLE_HEADLESS = "1"

# Set data directory (optional, defaults to "data")
$env:JOBS_SCRAPER_DATA_DIR = "data"
```

### Step 7: Start the API Server
```powershell
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

**The `--reload` flag enables auto-reload on code changes!**

You should see:
```
INFO:     Uvicorn running on http://0.0.0.0:8000 (Press CTRL+C to quit)
INFO:     Started reloader process
INFO:     Started server process
INFO:     Waiting for application startup.
INFO:     Application startup complete.
```

---

## Option 2: Docker (Matches Production)

### Prerequisites
- Docker Desktop installed
- Docker Compose (optional, but easier)

### Step 1: Build Docker Image
```powershell
cd w:\CodeBase\Resume-Projects\sumit-personal-site\job-search-api
docker build -t job-search-api .
```

### Step 2: Run Container
```powershell
docker run -p 8000:8000 -e ENABLE_HEADLESS=1 job-search-api
```

**Or with data directory:**
```powershell
docker run -p 8000:8000 -e ENABLE_HEADLESS=1 -v ${PWD}/data:/app/data job-search-api
```

---

## 🧪 Testing the API

### Test 1: Health Check
```powershell
Invoke-RestMethod -Uri "http://localhost:8000/health"
```

**Expected:**
```json
{
  "ok": true,
  "timestamp": "2026-02-20T..."
}
```

### Test 2: RSS Scrapers (Fast, ~30 seconds)
```powershell
Invoke-RestMethod -Uri "http://localhost:8000/debug"
```

**Expected:** JSON with 14 scrapers and job counts

### Test 3: Headless Scrapers (Slow, ~2-5 minutes)
```powershell
Invoke-RestMethod -Uri "http://localhost:8000/debug/headless" -TimeoutSec 300
```

**Expected:** JSON with 8 headless scrapers (LinkedIn, Indeed, Naukri, etc.)

**Note:** Takes 2-5 minutes! Each scraper has 90-second timeout.

### Test 4: Refresh Jobs (RSS Only - Fast)
```powershell
Invoke-RestMethod -Uri "http://localhost:8000/refresh?q=data%20analyst&days=3&headless=0" -Method Post
```

**Expected:** JSON with `ok: true`, `count: 200+`, `jobs: [...]`

### Test 5: Refresh Jobs (With Headless - Slow)
```powershell
Invoke-RestMethod -Uri "http://localhost:8000/refresh?q=data%20analyst&days=7&headless=1" -Method Post -TimeoutSec 600
```

**Expected:** JSON with `ok: true`, `count: 400+`, `jobs: [...]`

**Note:** Takes 2-5 minutes! Includes all 8 headless scrapers.

### Test 6: Get Jobs (Cached)
```powershell
Invoke-RestMethod -Uri "http://localhost:8000/jobs?limit=50"
```

**Expected:** JSON with cached jobs from `data/jobs.json`

### Test 7: Get Jobs with Filters
```powershell
# Filter by source
Invoke-RestMethod -Uri "http://localhost:8000/jobs?source=linkedin&limit=50"

# Filter by query
Invoke-RestMethod -Uri "http://localhost:8000/jobs?q=data%20scientist&limit=50"

# Sort by relevance
Invoke-RestMethod -Uri "http://localhost:8000/jobs?sort=relevance&limit=50"
```

---

## 🔍 Testing Headless Scrapers Individually

### Test LinkedIn Scraper
```powershell
# This will test just LinkedIn (modify debug/headless endpoint or test directly)
# Or check logs when running /debug/headless
```

### Check Logs
When running the server, you'll see logs like:
```
INFO: Scraped 15 jobs from linkedin
INFO: Scraped 20 jobs from indeed_headless
INFO: Scraped 10 jobs from naukri
```

---

## 🐛 Troubleshooting

### Issue 1: Playwright Not Found
**Error:** `playwright not installed` or `chromium not found`

**Fix:**
```powershell
python -m playwright install chromium
```

### Issue 2: Headless Scrapers Return 0 Jobs
**Possible Causes:**
- Sites blocking scrapers
- Selectors broken (site structure changed)
- Date filter too strict

**Debug:**
1. Check server logs for errors
2. Test with longer date range: `days=30`
3. Check if sites are accessible manually

### Issue 3: Port Already in Use
**Error:** `Address already in use`

**Fix:**
```powershell
# Use different port
uvicorn app.main:app --host 0.0.0.0 --port 8001 --reload

# Or kill process using port 8000
# Windows:
netstat -ano | findstr :8000
taskkill /PID <PID> /F
```

### Issue 4: Import Errors
**Error:** `ModuleNotFoundError`

**Fix:**
```powershell
# Make sure venv is activated
.venv\Scripts\Activate.ps1

# Reinstall dependencies
pip install -r requirements.txt
```

### Issue 5: Headless Scrapers Timeout
**Error:** Timeout after 90 seconds

**Normal:** Some scrapers may timeout if sites are slow or blocking
**Fix:** Check logs, try individual scrapers, or increase timeout in code

---

## 📊 Expected Results

### RSS Scrapers (`/debug`)
- **14 scrapers** should return jobs
- **200-300+ jobs** total
- **~30 seconds** execution time

### Headless Scrapers (`/debug/headless`)
- **8 scrapers** (LinkedIn, Indeed, Naukri, Hirist, Foundit, Shine, Monster, Glassdoor)
- **0-200 jobs per scraper** (may be 0 if sites blocking)
- **~2-5 minutes** execution time

### Refresh (`/refresh`)
- **RSS only:** 200-300 jobs, ~30-45 seconds
- **With headless:** 400-1000+ jobs, ~2-5 minutes

---

## 🎯 Quick Test Script

Create `test_local.ps1`:

```powershell
$baseUrl = "http://localhost:8000"

Write-Host "1. Testing /health..." -ForegroundColor Yellow
Invoke-RestMethod -Uri "$baseUrl/health" | ConvertTo-Json

Write-Host "`n2. Testing /debug (RSS scrapers)..." -ForegroundColor Yellow
$debug = Invoke-RestMethod -Uri "$baseUrl/debug" -TimeoutSec 60
Write-Host "Total jobs: $($debug.total_jobs)" -ForegroundColor Green

Write-Host "`n3. Testing /refresh (RSS only)..." -ForegroundColor Yellow
$refresh = Invoke-RestMethod -Uri "$baseUrl/refresh?q=data%20analyst&days=3&headless=0" -Method Post -TimeoutSec 120
Write-Host "Jobs scraped: $($refresh.count)" -ForegroundColor Green

Write-Host "`n4. Testing /jobs..." -ForegroundColor Yellow
$jobs = Invoke-RestMethod -Uri "$baseUrl/jobs?limit=10"
Write-Host "Jobs returned: $($jobs.count)" -ForegroundColor Green

Write-Host "`n✅ Local testing complete!" -ForegroundColor Green
```

Run it:
```powershell
.\test_local.ps1
```

---

## 🚀 Full Workflow

### 1. Start Server
```powershell
cd job-search-api
.venv\Scripts\Activate.ps1
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

### 2. In Another Terminal, Test RSS
```powershell
Invoke-RestMethod -Uri "http://localhost:8000/debug"
```

### 3. Test Headless (Optional, Slow)
```powershell
Invoke-RestMethod -Uri "http://localhost:8000/debug/headless" -TimeoutSec 300
```

### 4. Refresh Jobs
```powershell
Invoke-RestMethod -Uri "http://localhost:8000/refresh?q=data%20analyst&days=7&headless=0" -Method Post
```

### 5. Get Jobs
```powershell
Invoke-RestMethod -Uri "http://localhost:8000/jobs?limit=400"
```

---

## 📝 Notes

- **Docker is optional** - You can run directly with Python
- **Playwright required** - For headless scrapers (LinkedIn, Indeed, etc.)
- **Headless is slow** - Expect 2-5 minutes for all 8 scrapers
- **RSS is fast** - ~30 seconds for all 14 RSS sources
- **Auto-reload enabled** - Code changes auto-restart server (with `--reload`)
- **Data persists** - Jobs saved to `data/jobs.json` (local file)

---

## 🔗 Next Steps

1. **Test RSS scrapers** - Should work immediately
2. **Test headless scrapers** - May return 0 jobs (sites blocking)
3. **Check logs** - See what's happening
4. **Fix broken scrapers** - Update selectors if needed
5. **Test with frontend** - Point `jobs.html` to `http://localhost:8000`
