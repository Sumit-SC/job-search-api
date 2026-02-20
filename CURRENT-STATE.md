# Railway API & scraping — current state (honest)

**Bottom line:** The **live** jobs flow today is **Vercel → frontend**. Railway is built and deployable but **not** the primary API yet. Phase 1 (Railway as single source of truth) is **in progress**, not done.

---

## What’s actually used today

| Layer | What | Reality |
|-------|------|--------|
| **Frontend** | analytics-lab, playground jobs pages | **Uses Vercel only.** `window.JOB_PROXY_URL = 'https://playground-serveless.vercel.app'`. No Railway in the chain. |
| **API** | Jobs listing / refresh | **Vercel:** `GET /api/jobs-snapshot` (primary), `GET /api/jobs-cached`, `GET /api/jobs-refresh`. RSS + Remotive (+ optional headless from Vercel). |
| **Railway (job-search-api)** | Same idea, Python/FastAPI | **Built, not wired to frontend.** You can deploy it and call `GET /jobs`, `POST /refresh` yourself; the UI does not call it. |

So: **current working plan for “the product”** = Vercel APIs + static frontend. Railway is the **intended** backend once Phase 1 is solid.

---

## Railway API — what exists

**Endpoints (all implemented):**

- **GET /health** — Health check.
- **GET /jobs** — Read from **local JSON file** (`data/jobs.json`). Params: `q`, `days`, `limit`, `source`, optional `page`, `per_page`. No DB; file is created/updated only by `POST /refresh`.
- **POST /refresh** — Runs `scrape_all()` (all RSS/HTTP + optional headless), **overwrites** `data/jobs.json`, returns the same job list. Default `q=data analyst`, `days=3`.
- **GET /debug** — Runs a subset of scrapers (weworkremotely, jobscollider, remoteok, remotive_api, indeed_rss), returns counts; does not save.

**Storage:** File-based. `JOBS_SCRAPER_DATA_DIR` (default `data`), file `jobs.json`. On Railway, that’s ephemeral unless you use a Railway Postgres/Redis or external store — so a new deploy or restart can wipe stored jobs until the next `POST /refresh`.

**Scraping (job-search-api):**

- **RSS/HTTP (11 sources):** WeWorkRemotely, Jobscollider, RemoteOK, Remotive (API + RSS), Wellfound, Indeed RSS, Remote.co, Jobspresso, Himalayas, Authentic Jobs. Status: in code; lenient filters applied on some, others may still be strict — see SOURCES_STATUS.md.
- **Headless (Playwright):** LinkedIn, Indeed (browser), Naukri. Run only when `ENABLE_HEADLESS=1`. On Railway they can time out or get blocked; not guaranteed.

So the **current working plan for Railway** is: one app that can refresh (scrape) and serve jobs from a file; scraping is “best effort” from 11 RSS/HTTP + 3 headless, with known gaps.

---

## What’s *not* done (Railway)

- **Frontend** does not call Railway. To “use” Railway you’d change `JOB_PROXY_URL` to a proxy that talks to Railway, or point the frontend at Railway directly (CORS is open).
- **Persistent storage** on Railway: `data/jobs.json` is not durable by default; you’d need a Railway Postgres/Redis or S3/DB for real persistence.
- **API features from PREFERENCES:** Not implemented yet: `sort=relevance`, `yoe_min`/`yoe_max`, `match_score`, salary/currency, group-by-currency, visa keyword detection, skill-based matching. GET /jobs has only `q`, `days`, `limit`, `source`, `page`, `per_page`.
- **Job model:** No `match_score`, salary, or currency on the `Job` model in code yet.
- **More headless scrapers:** Hirist, Foundit, Glassdoor, Unstop, Shine, etc. are in the plan (PROJECT-PLAN.md, SOURCES_STATUS.md) but not in `scraper.py` yet.
- **Vercel → Railway:** No Vercel endpoint that proxies to Railway. So “switch to Railway” means changing the frontend (or adding a proxy) and deploying Railway.

---

## Intended plan (from PROJECT-PLAN.md)

1. **Phase 1 — Railway first:** Railway = single source of truth: fetch from 20+ sources, store jobs, expose GET /jobs and POST /refresh with proper filters/sort. Then test and deploy.
2. **Phase 2 (optional):** Vercel calls Railway (GET /jobs, POST /refresh), caches or proxies for the frontend.
3. **Phase 3:** Frontend (analytics-lab / playground) calls either Railway directly or Vercel → Railway.

We’re still in Phase 1: Railway can refresh and serve, but filters/sort/match_score/salary/currency and more headless sources are pending, and the frontend still uses Vercel only.

---

## Summary table

| Item | Status |
|------|--------|
| Railway app runs (health, jobs, refresh, debug) | ✅ Done |
| Storage (file-based) | ✅ Done (ephemeral on Railway unless you add Postgres/Redis/DB) |
| Pagination (page/per_page) on GET /jobs | ✅ Done |
| 11 RSS/HTTP scrapers in scrape_all | ✅ In code (quality varies by source) |
| 3 headless scrapers (LinkedIn, Indeed, Naukri) | ✅ In code (optional, may timeout on Railway) |
| Frontend uses Railway | ❌ No — uses Vercel |
| sort, yoe, match_score, salary, currency, visa, skill match | ❌ Not implemented |
| More headless (Hirist, Foundit, etc.) | ❌ Not added yet |
| Durable storage on Railway | ❌ Not implemented |

So: **current working plan** = Vercel for live traffic; Railway is the **target** backend with a clear path (Phase 1 → 2 → 3) but not yet the primary API or fully feature-complete.
