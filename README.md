# Jobs Scraper (Railway) – FastAPI + Playwright (planned)

**What this project is:** The **main Python job scraper** (FastAPI + Playwright): 11+ RSS/HTTP sources and optional headless scrapers (LinkedIn, Indeed, Naukri). Intended for **Railway** or any container host. Not used by the current Vercel + frontend; that uses **playground-serveless** job APIs. See [JOBS-SCRAPER.md](../JOBS-SCRAPER.md) in the base directory.

---

This is a separate scraper service intended to run on **Railway** (or any container host) where headless browsing works reliably.

## What it does (today)

- Provides a small API:
  - `GET /health`
  - `GET /jobs` (reads from local JSON store)
  - `POST /refresh` (scrapes and writes jobs to JSON store)

- **RSS/HTTP sources** (fast, stable, always active):
  - WeWorkRemotely RSS
  - RemoteOK RSS
  - Jobscollider RSS
  - Remotive (API + RSS)
  - Wellfound RSS (multiple feeds)
  - Indeed RSS
  - Remote.co RSS
  - Jobspresso RSS
  - Himalayas RSS
  - Authentic Jobs RSS

- **Playwright headless scrapers** (when `ENABLE_HEADLESS=1`):
  - LinkedIn Jobs
  - Indeed (headless browser)
  - Naukri.com (India)
  - More portals coming soon (Monster, Glassdoor, Hirist, etc.)

## What it will do next

- Add more Playwright scrapers for remaining portals (Monster, Foundit, Glassdoor, Hirist, JobsAaj, TimesJobs, Shine, ZipRecruiter, SimplyHired, CareerBuilder, Dice, Adzuna, Jooble, Freshersworld).
- Store results in a proper DB (Neon/Supabase Postgres) instead of a local JSON file.

See **[SOURCES_STATUS.md](SOURCES_STATUS.md)** for the full list of 17–20 boards, what’s working, and the plan (RSS → headless → tests → UI).

## Run locally

1. Create a venv and install deps:

```bash
python -m venv .venv
source .venv/bin/activate  # Windows PowerShell: .venv\Scripts\Activate.ps1
pip install -r requirements.txt
python -m playwright install chromium
```

2. Start API:

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

3. Refresh and fetch jobs:

```bash
curl -X POST "http://localhost:8000/refresh?q=data%20analyst&days=3"
curl "http://localhost:8000/jobs?days=3&limit=50"
```

## Deploy to Railway

### Step 1: Create Railway Project
- Go to [Railway.app](https://railway.app) and create a new project
- Select "Deploy from GitHub repo"
- Choose `job-search-api` repository

### Step 2: Add Persistent Storage (Optional)

**Note:** Railway doesn't have volumes. For persistent storage, use one of these options:

**Option A: Railway Postgres (Recommended)**
1. In Railway dashboard → "New" → "Database" → "Add Postgres"
2. Railway automatically sets `DATABASE_URL` environment variable
3. Update `storage.py` to use Postgres instead of JSON file
4. Benefits: True persistence, better querying, scales well

**Option B: Railway Redis (For Caching)**
1. In Railway dashboard → "New" → "Database" → "Add Redis"
2. Railway automatically sets `REDIS_URL` environment variable
3. Update `storage.py` to use Redis for caching
4. Benefits: Fast caching, persists between requests

**Option C: Use `/refresh` Directly (No Storage)**
- Call `/refresh` endpoint directly from your UI
- No database setup needed, but slower (30-45s per request)

### Step 3: Environment Variables
In your Railway service settings, add:

```
JOBS_SCRAPER_DATA_DIR=/app/data  # Only needed if using file storage (ephemeral)
ENABLE_HEADLESS=1
```

**Note:** If using Postgres or Redis, you don't need `JOBS_SCRAPER_DATA_DIR` - update `storage.py` to use the database instead.

### Step 4: Deploy
Railway will auto-detect the Dockerfile and deploy. The start command is already configured in the Dockerfile.

### Step 5: Test
Once deployed, test the API. From the repo (local or CI):

**PowerShell (Windows):**
```powershell
cd job-search-api/scripts
.\test_railway.ps1 https://your-app.up.railway.app
```

**Bash (Linux/macOS):**
```bash
cd job-search-api/scripts
chmod +x test_railway.sh
./test_railway.sh https://your-app.up.railway.app
```

**Manual curls:** 
- Health: `GET /health`
- System resources: `GET /system`
- RSS scrapers: `GET /debug`
- Headless scrapers: `GET /debug/headless` (slow, ~2-5 min)
- Refresh (RSS only, fast): `POST /refresh?days=3&headless=0`
- Refresh (with headless): `POST /refresh?days=3`
- List jobs: `GET /jobs?limit=50`
