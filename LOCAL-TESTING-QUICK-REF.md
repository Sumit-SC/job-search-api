# Local Testing Quick Reference

## ✅ Setup Complete!

Your local API server is now running at **http://localhost:8000**

## Quick Test Commands

### 1. Check if server is running
```powershell
curl http://localhost:8000/jobs?limit=5
```

### 2. View API documentation
Open in browser: **http://localhost:8000/docs**

### 3. Test endpoints

**Get jobs:**
```powershell
curl http://localhost:8000/jobs?limit=10
```

**Refresh jobs (RSS only, fast):**
```powershell
curl -X POST "http://localhost:8000/refresh?q=data%20analyst&days=3&headless=0"
```

**Test headless scrapers (slow, 2-5 min):**
```powershell
curl http://localhost:8000/debug/headless
```

**System info:**
```powershell
curl http://localhost:8000/system
```

### 4. Run automated test script
```powershell
.\test_local.ps1
```

## Environment Variables Set

- `JOBS_SCRAPER_DATA_DIR=data` (jobs stored in `data/jobs.json`)
- `ENABLE_HEADLESS=1` (headless scrapers enabled)

## Stop the Server

Press `Ctrl+C` in the terminal where the server is running, or close that terminal window.

## Start the Server Again

```powershell
cd w:\CodeBase\Resume-Projects\sumit-personal-site\job-search-api
.venv\Scripts\Activate.ps1
$env:JOBS_SCRAPER_DATA_DIR = "data"
$env:ENABLE_HEADLESS = "1"
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

## Test with Frontend

Update `analytics-lab/assets/js/jobs.js` to use local API:
```javascript
window.JOB_PROXY_URL = "http://localhost:8000";
```

Then open `analytics-lab/jobs.html` in your browser.

## Notes

- Server runs with `--reload` flag, so code changes will auto-restart the server
- Jobs are stored in `data/jobs.json` (ephemeral - will be lost when you delete the file)
- Headless scrapers require Playwright browsers (already installed)
- RSS scrapers work immediately without any setup
