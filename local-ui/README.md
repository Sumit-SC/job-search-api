# Job Search API — Local UI

Web UI for the Job Search API: refresh jobs, search/filter, RSSJobs.app, JobSpy, JobSpy.tech embed, Interview Prep, and a password-protected **Monitor** page (health + API docs + test buttons).

---

## Features

- **Refresh:** Scrape jobs (RSS + optional headless) and save to the API’s store.
- **Search & filter:** Free text, days, source, YOE, sort, limit.
- **Pages:** Core API (`index.html`), RSSJobs, JobSpy, JobSpy.tech, Interview Prep.
- **Monitor:** `/ui/monitor.html` — health checks, endpoint list, Test buttons, link to Swagger UI. Requires `MONITOR_SECRET` set on the server (see main [README](../README.md)).
- **Theme:** Dark/light toggle (🌙/☀️) and low-profile admin link (🔧/⚙️) to Monitor in the header on all pages.

---

## Usage

### 1. Start the API

```powershell
cd path\to\job-search-api
.venv\Scripts\Activate.ps1
$env:JOBS_SCRAPER_DATA_DIR = "data"
$env:ENABLE_HEADLESS = "1"
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

### 2. Open the UI

- **Local:** Open `index.html` in a browser, or go to **http://localhost:8000/ui/** once the API is running.
- **Railway:** `https://your-app.up.railway.app/ui/`. For Monitor, set `MONITOR_SECRET` in Railway Variables and enter it on the monitor page.

### 3. Monitor page

Open **Monitor** (link in top-right or `/ui/monitor.html`), enter the **monitor secret** (same as `MONITOR_SECRET` on the server), then use the dashboard and the **API endpoints** table to test endpoints. Full API docs: **Open Swagger UI** → `/docs`.

---

## Configuration

To use a different API base URL (e.g. another host/port), set it in the relevant JS file (e.g. `app.js`). When served by the FastAPI app at `/ui/`, the UI uses the same origin, so no change is needed for production.

---

## File structure

```
local-ui/
├── index.html          # Core API (refresh + search)
├── rssjobs.html        # RSSJobs.app
├── jobspy.html         # JobSpy
├── jobspy-tech.html    # JobSpy.tech embed
├── interview-prep.html # Interview prep + ChatGPT prompt
├── monitor.html        # Health dashboard + API docs + test buttons
├── styles.css          # Shared styles (incl. dark theme)
├── theme.js            # Dark/light toggle + admin link
├── app.js              # Core API logic
├── jobspy.js           # JobSpy page logic
├── interview-prep.js   # Interview prep logic
├── analytics.js        # Optional analytics
└── README.md           # This file
```

---

## Troubleshooting

| Issue | Check |
|-------|--------|
| "Failed to fetch" | API running on the expected host/port (default 8000). CORS is enabled. |
| No jobs | Run **Refresh** first; increase **Days** or try different filters. |
| Monitor "Invalid key" | Set `MONITOR_SECRET` in Railway (or your server) and use the same value on the page. |
| UI or theme broken | Ensure `styles.css` and `theme.js` are loaded; check the browser console. |
