# Railway API & scraping — current state

**Bottom line:** The **live** jobs flow today is **Vercel → frontend**. Railway is built and deployable but **not** the primary API yet. Phase 1 (Railway as single source of truth) is **in progress**, not done.

---

## What's actually used today

| Layer | What | Reality |
|-------|------|--------|
| **Frontend** | analytics-lab, playground jobs pages | **Uses Vercel only.** `window.JOB_PROXY_URL = 'https://playground-serveless.vercel.app'`. Railway can be selected as a backend in the UI but is not the default. |
| **API** | Jobs listing / refresh | **Vercel:** `GET /api/jobs-snapshot` (primary), `GET /api/jobs-cached`, `GET /api/jobs-refresh`. RSS + Remotive + HiringCafe + Arbeitnow + Jobicy + WorkingNomads (+ optional headless from Vercel). |
| **Railway (job-search-api)** | Same idea, Python/FastAPI | **Built, wirable from frontend.** You can deploy it and call `GET /jobs`, `POST /refresh` yourself; the UI has a Railway backend toggle. |

So: **current working plan for "the product"** = Vercel APIs + static frontend. Railway is the **intended** backend once Phase 1 is solid.

---

## Railway API — what exists

**Endpoints (all implemented):**

- **GET /health** — Health check.
- **GET /jobs** — Read from **local JSON file** (`data/jobs.json`). Params: `q`, `days`, `limit`, `source`, optional `page`, `per_page`. No DB; file is created/updated only by `POST /refresh`.
- **POST /refresh** — Runs `scrape_all()` (all RSS/HTTP + optional headless), **overwrites** `data/jobs.json`, returns the same job list. Params: `q` (default `data analyst`), `days` (default 3), `sources` (comma-separated list to filter scrapers).
- **GET /debug** — Runs all scrapers from `SCRAPER_REGISTRY`, returns counts; does not save.

**Storage:** File-based. `JOBS_SCRAPER_DATA_DIR` (default `data`), file `jobs.json`. On Railway, that's ephemeral unless you use a Railway volume, Postgres, or Redis — so a new deploy or restart can wipe stored jobs until the next `POST /refresh`.

**Scraping (job-search-api):**

- **RSS/HTTP (22 sources via SCRAPER_REGISTRY):** Greenhouse, Lever, WeWorkRemotely, Jobscollider (x2), RemoteOK, HN Jobs, Remotive (API + RSS + data feed + AI/ML feed), Wellfound, Indeed RSS, Remote.co, Jobspresso, Himalayas, Authentic Jobs, StackOverflow, Hiring.cafe, Arbeitnow, Jobicy, WorkingNomads. 
- **Headless (8 Playwright scrapers):** LinkedIn, Indeed (browser), Naukri, Hirist, Foundit, Shine, Monster, Glassdoor. Run only when `ENABLE_HEADLESS=1`. On Railway they can time out or get blocked; not guaranteed.
- **Sources filter:** `POST /refresh?sources=remoteok,remotive` only runs the listed scrapers. Works for both RSS/HTTP and headless scrapers.

---

## What's *not* done (Railway)

- **Frontend** defaults to Vercel. To "use" Railway, select it in the UI settings or change `JOB_PROXY_URL`.
- **Persistent storage** on Railway: `data/jobs.json` is not durable by default; you'd need a Railway volume, Postgres, Redis, or S3 for real persistence.
- **Durable storage integration** (Postgres/Redis/S3) — not implemented.
- **Vercel → Railway proxy:** No Vercel endpoint that proxies to Railway yet.

---

## Summary table

| Item | Status |
|------|--------|
| Railway app runs (health, jobs, refresh, debug) | Done |
| Storage (file-based) | Done (ephemeral on Railway unless you add a volume) |
| Pagination (page/per_page) on GET /jobs | Done |
| 22 RSS/HTTP scrapers in SCRAPER_REGISTRY | Done |
| 8 headless scrapers (LinkedIn, Indeed, Naukri, Hirist, Foundit, Shine, Monster, Glassdoor) | Done (optional, may timeout) |
| Sources filter on /refresh | Done |
| .env.example | Done |
| Local UI sources selector | Done |
| Frontend uses Railway | Optional (selectable, not default) |
| Durable storage on Railway | Not implemented |

So: **current working plan** = Vercel for live traffic; Railway is the **target** backend with a clear path (Phase 1 → 2 → 3) but not yet the primary API.
