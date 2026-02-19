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

### Step 2: Add Persistent Storage (Volume)
Railway uses **Volumes** for persistent storage:

**Method A - Command Palette:**
1. Press `Ctrl+K` (or `Cmd+K` on Mac) in Railway dashboard
2. Type "volume" and select "Create Volume"
3. Select your `job-search-api` service
4. Set mount path to: `/app/data`

**Method B - Right-click:**
1. Right-click on your service card in Railway dashboard
2. Select "Create Volume" or "Add Volume"
3. Set mount path to: `/app/data`

### Step 3: Environment Variables
In your Railway service settings, add:

```
JOBS_SCRAPER_DATA_DIR=/app/data
ENABLE_HEADLESS=1
```

### Step 4: Deploy
Railway will auto-detect the Dockerfile and deploy. The start command is already configured in the Dockerfile.

### Step 5: Test
Once deployed, test the API:
- Health: `GET https://your-app.up.railway.app/health`
- Refresh jobs: `POST https://your-app.up.railway.app/refresh?q=data%20analyst&days=3`
- Get jobs: `GET https://your-app.up.railway.app/jobs?days=3&limit=50`
