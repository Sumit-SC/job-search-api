# Job Search API — FastAPI + Playwright

Python job scraper service: 11+ RSS/HTTP sources and optional headless scrapers (LinkedIn, Indeed, Naukri). Built for **Railway** or any container host. The repo also serves a local UI at `/ui/` (Core API, RSSJobs, JobSpy, Interview Prep, Monitor).

---

## Contents

- [What it does](#what-it-does)
- [Run locally](#run-locally)
- [Deploy to Railway](#deploy-to-railway)
- [Environment variables](#environment-variables)
- [Monitor & API docs](#monitor--api-docs)
- [Roadmap](#roadmap)

---

## What it does

| Area | Details |
|------|---------|
| **API** | `GET /health`, `GET /jobs`, `POST /refresh`, RSS feed, grouped/salary endpoints, system info |
| **RSS/HTTP** | WeWorkRemotely, RemoteOK, Jobscollider, Remotive, Wellfound, Indeed, Remote.co, Jobspresso, Himalayas, Authentic Jobs |
| **Headless** (when `ENABLE_HEADLESS=1`) | LinkedIn Jobs, Indeed, Naukri.com; more planned (Monster, Glassdoor, etc.) |
| **UI** | `/ui/` — Core API, RSSJobs.app, JobSpy, JobSpy.tech embed, Interview Prep; `/ui/monitor.html` — password-protected health & API docs |

See **[SOURCES_STATUS.md](SOURCES_STATUS.md)** for board status and **[JOBS-SCRAPER.md](../JOBS-SCRAPER.md)** for how this fits with the rest of the workspace.

---

## Run locally

```bash
python -m venv .venv
# Windows: .venv\Scripts\Activate.ps1  |  macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
python -m playwright install chromium
```

Set env (optional): `JOBS_SCRAPER_DATA_DIR=data`, `ENABLE_HEADLESS=1`. Then:

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

- **UI:** http://localhost:8000/ui/  
- **Refresh jobs:** `POST /refresh?q=data%20analyst&days=3`  
- **List jobs:** `GET /jobs?days=3&limit=50`

---

## Deploy to Railway

### 1. Create project

- [Railway.app](https://railway.app) → **New Project** → **Deploy from GitHub repo** → select `job-search-api`.

### 2. Set environment variables

In the Railway dashboard:

1. Open your **project** → select the **service** (your app).
2. Go to the **Variables** tab.
3. Click **+ New Variable** (or **Add Variable**) and add each variable below. Use **RAW** mode to paste multiple lines if needed.

| Variable | Required | Description |
|----------|----------|-------------|
| `MONITOR_SECRET` | **Yes** (for monitor) | Secret string to access `/ui/monitor.html` and `GET /api/monitor`. Use a long random password; never commit it. |
| `JOBS_SCRAPER_DATA_DIR` | No | Directory for JSON job store (default `data`). On Railway you can use `/app/data` (ephemeral unless you add a volume). |
| `ENABLE_HEADLESS` | No | Set to `1` to enable Playwright scrapers (LinkedIn, Indeed, Naukri). Default `1`. Use `0` for RSS-only. |
| `USE_JOBSPY` | No | Set to `1` to use jobspy library where applicable. Default `0`. |

**Example (minimal for monitor + file storage):**

- `MONITOR_SECRET` = `<your-secret-password>`
- `JOBS_SCRAPER_DATA_DIR` = `/app/data`
- `ENABLE_HEADLESS` = `1`

Railway may auto-inject `PORT`, `RAILWAY_*`; you don’t need to set those.

### 3. Storage (optional)

- **File storage (default):** Jobs are stored in `JOBS_SCRAPER_DATA_DIR`. On Railway this is ephemeral unless you attach a volume (if available).
- **Postgres/Redis:** Add via Railway **New → Database**. You’d then need to point `storage.py` at the DB; currently the app uses file storage.

### 4. Deploy

Railway detects the Dockerfile and deploys. Start command is set in the Dockerfile.

### 5. Test

- **Health:** `GET https://your-app.up.railway.app/health`
- **Jobs:** `GET https://your-app.up.railway.app/jobs?limit=50`
- **Refresh:** `POST https://your-app.up.railway.app/refresh?days=3&headless=0`
- **Scripts:** `job-search-api/scripts/test_railway.ps1` (Windows) or `test_railway.sh` (Bash) with your app URL.

---

## Environment variables

Summary (see [Deploy → Set environment variables](#2-set-environment-variables) for how to set them on Railway):

| Variable | Default | Purpose |
|----------|---------|---------|
| `MONITOR_SECRET` | *(none)* | Password for `/ui/monitor.html` and `/api/monitor`. **Set on Railway** so the monitor and API-docs page work. |
| `JOBS_SCRAPER_DATA_DIR` | `data` | Directory for the JSON job file. |
| `ENABLE_HEADLESS` | `1` | `1` = enable Playwright scrapers; `0` = RSS only. |
| `USE_JOBSPY` | `0` | `1` = use jobspy where applicable. |

---

## Monitor & API docs

- **Monitor URL:** `https://your-app.up.railway.app/ui/monitor.html`
- **Access:** Enter the same value you set for **`MONITOR_SECRET`** (in Railway → Variables). You can also pass it in the URL: `.../monitor.html?key=YOUR_SECRET` (avoid sharing that link).
- **What it shows:** Health checks, job DB status, endpoint latencies, cache stats, **list of API endpoints** (method, path, description), **Test** button per endpoint (result shown below), and a link to **Swagger UI** (`/docs`) for full API documentation.

If `MONITOR_SECRET` is not set on the server, `GET /api/monitor` returns **503**.

---

## Roadmap

- More Playwright scrapers (Monster, Foundit, Glassdoor, Hirist, etc.).
- Persist jobs in Postgres/Neon instead of JSON when desired.

---

## License

Same as the parent workspace.
