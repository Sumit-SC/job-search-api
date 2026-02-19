# Job Scraper API — Project plan & progress

**Goal:** One API (Railway) that fetches jobs from 20+ sources (RSS, HTTP APIs, headless browser), with filters/sort for your roles and preferences. Then optionally expose via Vercel and connect to the frontend.

---

## Architecture (simplified)

| Phase | What | Status |
|-------|------|--------|
| **1. Railway first** | Make job-search-api on Railway the **single source of truth**: fetch from all sources, store jobs, expose `GET /jobs` and `POST /refresh`. Filters (query, days, source) and sort (date, relevance) work here. | 🔲 In progress |
| **2. Vercel (optional)** | If needed: Vercel serverless calls Railway (`GET /jobs`, `POST /refresh`) and caches or proxies for the frontend. | 🔲 Later |
| **3. Frontend** | GitHub Pages (or analytics-lab) calls either Railway directly or Vercel → Railway. One clear chain: UI → API → Railway scraper. | 🔲 After 1 (and 2 if used) |

Current pain: three different layers (GitHub Pages, Vercel, Railway) with unclear flow. **Phase 1** is: Railway fetches and serves results as intended; no frontend/Vercel dependency until that works.

---

## Target: 20+ job sources

### RSS / HTTP (11 sources) — in code, need lenient filters + test

| # | Source | Type | Notes |
|---|--------|------|--------|
| 1 | WeWorkRemotely | RSS | Lenient filter applied |
| 2 | Jobscollider | RSS | Lenient filter |
| 3 | RemoteOK | RSS | Datetime fix applied |
| 4 | Remotive | API + RSS | Lenient filter |
| 5 | Wellfound | RSS | Multiple feeds |
| 6 | Indeed | RSS | Relaxing |
| 7 | Remote.co | RSS | |
| 8 | Jobspresso | RSS | |
| 9 | Himalayas | RSS | |
| 10 | Authentic Jobs | RSS | |
| 11 | (Remotive RSS variants) | RSS | Same as 4 |

### Headless / Playwright (priority order)

| # | Source | Status | Notes |
|---|--------|--------|--------|
| 12 | LinkedIn | In code | Keep; good for data roles |
| 13 | Indeed (browser) | In code | Keep |
| 14 | Naukri | In code | Keep |
| 15 | Glassdoor | Add | Decent jobs for data roles |
| 16 | Hirist | Add (priority) | Active postings |
| 17 | Wellfound | RSS in code; headless if needed | Active postings |
| 18 | Foundit | Add (priority) | Active postings |
| 19 | Unstop | Add | Then Shine |
| 20 | Shine | Add | |
| 21+ | Monster, TimesJobs, etc. | As needed | 2026 job market |

---

## Search, filter & sort (confirmed)

**Full details:** [PREFERENCES.md](PREFERENCES.md) — single source of truth.

**Summary:**

- **Roles:** Tier 1 = analyst roles + broad “analyst” for more results. Tier 2 = DS, ML Engineer, Junior/Associate ML Engineer, Junior/Associate Data Engineer. Data domain only (analyst + science); junior/associate/intern OK for Data Engineer, not for others unless data-focused. Exclude 5+ YOE.
- **Experience:** Primary 2–3 (mid-level); API supports bands 0–2, 1–4, 2–3. Hard rule: avoid 5+ YOE.
- **Location:** (1) Remote worldwide, (2) Remote India, (3) Indian cities: Pune, Hyderabad, Mumbai, Thane, Navi Mumbai, Bangalore, Chennai, Delhi/NCR. (4) Foreign with sponsored visa (Japan, EU, Korea, US, Gulf).
- **Mode:** Remote first; open to relocation to preferred cities.
- **Default query:** “analyst”. UI: role filter (dropdown) to narrow down.
- **Sort:** Newest first (default); relevance; manual toggle (sort=date | relevance | source). Salary: group by currency (INR → USD → GBP → SGD).
- **Must-have:** Every job has **actual apply/posting URL**; API returns **match %** (fit from YOE, skills, role, location). Job type: full-time default, include all (contract, part-time, internship) with filter.

---

## Progress log

| Date | Done | Next |
|------|------|------|
| *(start)* | Project plan created. Railway = Phase 1. | — |
| *(confirmed)* | **Preferences locked** in [PREFERENCES.md](PREFERENCES.md): roles, YOE, location, sort, salary grouping, apply links, match %. Headless priority: Hirist, Wellfound, Foundit, Unstop, Shine; keep LinkedIn, Naukri, Indeed; add Glassdoor. | Implement: lenient filters on RSS/HTTP; add `sort`, `experience_band`, `apply_url`, `match_score`; currency grouping; then headless scrapers in priority order. |

---

## Next steps (Phase 1)

1. **Code:** Lenient date + query logic on all 11 RSS/HTTP scrapers; ensure each job has **apply/posting URL**.
2. **API:** Add `sort` (date | relevance | source), optional `yoe_min`/`yoe_max` or `experience_band`; exclude 5+ YOE; return **match_score** (fit %); salary/currency for grouping (INR, USD, GBP, SGD).
3. **Scrapers:** Add headless: Glassdoor, Hirist, Foundit, Unstop, Shine (priority order); keep LinkedIn, Naukri, Indeed.
4. **Test:** `/debug`, `/refresh`, `GET /jobs` locally; then deploy to Railway.
5. **Docs:** Keep SOURCES_STATUS.md, PREFERENCES.md, and this file updated.

Once Railway is solid, connect frontend (and optional Vercel proxy).
