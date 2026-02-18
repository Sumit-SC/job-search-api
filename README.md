# Jobs Scraper (Railway) – FastAPI + Playwright (planned)

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

## Deploy to Railway (outline)

- Create a new Railway project from this folder.
- Set start command:

```bash
uvicorn app.main:app --host 0.0.0.0 --port $PORT
```

- Optionally set `JOBS_SCRAPER_DATA_DIR=/data` (or use a DB).
