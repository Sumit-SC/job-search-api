# Deploy `job-search-api` on Koyeb (no credit card)

This repo ships with a Dockerfile, so you can deploy on any Docker-capable host.

## Create the service

1. Create a Koyeb account.
2. **Create App** → **Deploy from GitHub** (or Docker image).
3. Select this repo and set **root directory** to `job-search-api` if prompted.
4. Build type: **Dockerfile**
5. Exposed port: **8000** (Koyeb will set `PORT` automatically; we support both).

## Environment variables (copy/paste)

Minimum recommended:

- `MONITOR_SECRET` = `<set-a-password>` (required to use `/ui/monitor.html`)

Recommended (free-tier stability):

- `ENABLE_HEADLESS` = `0` (headless scraping is expensive; keep RSS/API only)
- `USE_JOBSPY` = `0` (JobSpy works but can be slow / blocked; enable only when needed)
- `SCRAPER_CONCURRENCY` = `3`
- `JOBS_SCRAPER_DATA_DIR` = `/app/data`

Optional (board expansion):

- `GREENHOUSE_BOARDS` = `stripe,airtable` (example)
- `LEVER_BOARDS` = `netflix,figma` (example)
- `JOB_PROXY_URLS` = `http://user:pass@host:port,...` (only if you use headless and need proxies)

## What you need to “remake” from Railway

Railway-specific vars (like `RAILWAY_*`) are not needed.
Only the app-level vars matter:

- `MONITOR_SECRET` (recommended)
- `ENABLE_HEADLESS`, `USE_JOBSPY`, `SCRAPER_CONCURRENCY`
- `JOBS_SCRAPER_DATA_DIR`
- `GREENHOUSE_BOARDS`, `LEVER_BOARDS`
- `JOB_PROXY_URLS` (optional)

## Frontend (analytics-lab)

After deploy, copy your app URL (e.g. `https://your-service-xxx.koyeb.app`) into:

- `analytics-lab/pages/jobs.html` — set `window.JOB_SEARCH_API_BASE` (same line as `YOUR-APP.koyeb.app` placeholder).
- Optional: `analytics-lab/pages/test-analytics.html` — same variable for the API test section.

On the Jobs page, choose **Backend → Koyeb**; the UI sets `window.JOB_PROXY_URL` to that base. Vercel (playground-serveless) remains the other radio option.

## Test after deploy

- `GET /health`
- `GET /debug` (fast; validates RSS/API scrapers)
- `POST /refresh?q=data%20analyst&days=7&mode=rss` then `GET /jobs?days=7&limit=50`
- UI: `/ui/`
- Monitor: `/ui/monitor.html` (enter `MONITOR_SECRET`)

