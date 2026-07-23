# Hosting options for job-search-api (RAM, Workers, free tier)

**TL;DR:** Railway with low RAM is fine for **RSS/HTTP-only** scraping. For **headless (Playwright)** you need more RAM (512MB–1GB+) or a different platform. Cloudflare Workers can do **lightweight fetch-only** (RSS + APIs, no Playwright). Vercel runs Node/Python serverless (no Docker); best free tiers for “Python + optional Playwright” elsewhere.

---

## Railway (~100MB–1GB RAM)

- **Free trial:** ~$5 credit, then pay-as-you-go; some plans let you set RAM (e.g. 512MB–1GB).
- **~100MB RAM:** Enough for **FastAPI + RSS/HTTP scrapers only** (no Playwright). Your 11 RSS/API sources are just HTTP calls + parsing; they fit.
- **Headless (Playwright):** Chromium often needs **300–500MB+**. So with 100MB you **cannot** run headless reliably. With 512MB it’s borderline; 1GB is safer.
- **Practical:** On tight RAM, set `ENABLE_HEADLESS=0` (or omit it) so only RSS/HTTP run. That keeps the “workers” (scrapers) working within limit.

---

## Cloudflare Workers as a fetch layer

- **Idea:** Use a Worker to **fetch** job data (RSS + Remotive API, etc.) and return JSON. No Playwright, no Python runtime on Workers (Python is beta, limits apply).
- **Works for:** Lightweight aggregation — Worker calls 5–10 RSS feeds + 1–2 APIs, parses, returns one JSON. Your frontend or another backend calls the Worker.
- **Limits (free):** 128MB memory, **10ms CPU** per request, 100k requests/day. 10ms is very tight for multiple fetches; you might hit CPU or subrequest limits. **Paid:** 30s CPU, more subrequests — then Workers are a good “fetch-only” option.
- **Verdict:** Good **option** for a small, fast “fetch jobs from RSS/APIs” endpoint. Does **not** replace full job-search-api (no Python, no Playwright, no file storage). Can sit in front of or beside your current Vercel/Railway setup.

---

## Vercel (you have 8GB / good RAM)

- **Reality:** Vercel is **serverless**. Each function can have **up to 2GB RAM** (Hobby) or 4GB (Pro). There is **no** long-running Docker container; you get per-request execution.
- **Python:** Supported. You can run Python serverless functions. So “Python doesn’t work” is wrong — **Python works**. What doesn’t work is **running a full FastAPI app as a single long-running process** or **Docker** on Vercel’s standard offering.
- **Playwright on Vercel:** Possible inside a serverless function (e.g. one endpoint that launches headless, scrapes, returns). Downsides: cold starts, 250MB bundle limit, timeout (e.g. 300s). Your current **Node** `jobs-snapshot` already runs on Vercel and does RSS + API; that’s the right fit. Adding heavy Playwright in the same project is possible but costly and fragile.
- **8GB:** That’s likely **total** account/build resources or a different product (e.g. Vercel’s own infra), not “8GB per function.” Per-function cap is 2GB/4GB as above.

---

## Better free-tier platforms for “Python + optional Playwright”

| Platform        | Free tier RAM        | Docker | Playwright | Notes |
|----------------|----------------------|--------|------------|--------|
| **Render**     | 512MB                | Yes    | Tight      | Free tier: 750 hrs/month, **spins down after 15 min** (cold start). RSS-only fits; headless possible with Docker but 512MB is tight. |
| **Fly.io**     | Legacy only (256MB×3) | Yes   | Tight      | **New signups (Oct 2024+)** are pay-as-you-go — no real free tier. Legacy users get 3×256MB. |
| **Google Cloud Run** | 256MB default, up to 2GB | Yes | Yes | **Free tier:** 2M requests/month, 360k vCPU-seconds. Good for Docker + Python; increase memory for Playwright. |
| **Oracle Cloud Always Free** | 1–4 GB (ARM VMs) | You install | Yes | **Best free RAM.** You get a small VM; install Docker/Python yourself. More setup, no “one-click” deploy. |
| **Koyeb**      | Free tier available  | Yes    | Depends    | Check current free limits; can run Docker. |
| **Railway**    | Pay after trial      | Yes    | If RAM ≥ 512MB | Use RSS-only if RAM is ~100MB; consider 512MB–1GB for headless. |

**Recommendation for “good free tier to try”:**

1. **RSS/HTTP only (no headless):** Railway at low RAM, or **Cloudflare Workers** (fetch-only, JS or Python beta) if you’re OK with 10ms CPU / paid for more.
2. **Python + optional Playwright, free:** **Render** (accept spin-down + 512MB) or **Google Cloud Run** (free tier, bump memory for Playwright). **Oracle Always Free** if you want max RAM and can manage a VM.

---

## Summary

- **Railway:** Workers (scrapers) **work** if you stay **RSS/HTTP-only** on ~100MB; for headless you need more RAM or disable it.
- **Cloudflare Workers:** Good **option** for a lightweight “fetch searches” (RSS + APIs) endpoint; does not run full Python app or Playwright; free tier is tight (10ms CPU).
- **Vercel:** Python and 2GB per function are fine; Docker/long-running FastAPI process is not the model. Use it for serverless (like your current jobs-snapshot).
- **Best free for Python + Playwright:** Render (512MB, spin-down), Google Cloud Run (free tier, configurable RAM), or Oracle Always Free (VM with most RAM, more ops).
