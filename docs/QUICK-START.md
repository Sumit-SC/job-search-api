# Quick Start - Local Testing

**Fastest way to get the API running locally**

---

## ⚡ Quick Setup (5 minutes)

### 1. Install Dependencies
```powershell
cd w:\CodeBase\Resume-Projects\sumit-personal-site\job-search-api
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python -m playwright install chromium
```

### 2. Start Server
```powershell
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

### 3. Test It
```powershell
# In another terminal
Invoke-RestMethod -Uri "http://localhost:8000/health"
```

**That's it!** The API is running locally.

---

## 🧪 Quick Tests

### Test RSS Scrapers (Fast)
```powershell
Invoke-RestMethod -Uri "http://localhost:8000/debug"
```

### Test Headless Scrapers (Slow - 2-5 min)
```powershell
Invoke-RestMethod -Uri "http://localhost:8000/debug/headless" -TimeoutSec 300
```

### Scrape Jobs (RSS Only - Fast)
```powershell
Invoke-RestMethod -Uri "http://localhost:8000/refresh?q=data%20analyst&days=3&headless=0" -Method Post
```

### Get Jobs
```powershell
Invoke-RestMethod -Uri "http://localhost:8000/jobs?limit=50"
```

---

## 🐳 Docker (Optional)

**You DON'T need Docker** - Python works fine!

But if you want to use Docker:

```powershell
docker build -t job-search-api .
docker run -p 8000:8000 -e ENABLE_HEADLESS=1 job-search-api
```

---

## 📋 What You Need

- ✅ Python 3.9+
- ✅ Internet connection (for scraping)
- ❌ Docker (optional, not required)

---

## 🎯 Full Testing Script

Run the automated test script:

```powershell
.\test_local.ps1
```

This tests all endpoints automatically!

---

## 🔍 Check Headless Scrapers

To see which headless scrapers work:

```powershell
Invoke-RestMethod -Uri "http://localhost:8000/debug/headless" -TimeoutSec 300 | ConvertTo-Json -Depth 10
```

Look for `"ok": true` and `"count" > 0` for working scrapers.

---

## 📝 Notes

- **Headless scrapers are slow** - 2-5 minutes for all 8
- **RSS scrapers are fast** - ~30 seconds for all 14
- **Data saves to** `data/jobs.json` locally
- **Auto-reload enabled** - Code changes restart server automatically

---

## 🚀 Next: Test with Frontend

1. Start API: `uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload`
2. Open `analytics-lab/jobs.html` in browser
3. Change API backend toggle to "Railway"
4. Update `JOB_PROXY_URL` in console: `window.JOB_PROXY_URL = 'http://localhost:8000'`
5. Click Refresh - jobs should load from local API!
