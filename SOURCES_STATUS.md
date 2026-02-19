# Job boards: status and plan

## Why only 4 sources were returning data (FIXED)

**Problems:**
1. **Query filter too strict** – Filtered out jobs that didn't exactly match "data analyst"
2. **Missing headless scrapers** – Only 3 headless scrapers (LinkedIn, Indeed, Naukri), missing Hirist, Foundit, Monster, Glassdoor
3. **Missing RSS sources** – Only 11 RSS sources, missing Remotive category feeds and Stack Overflow
4. **Headless limits too low** – Stopped at 30 jobs per scraper

**Fixes Applied:**
1. ✅ **Very lenient query filter** – Generic queries match almost everything with data context
2. ✅ **Added 5 headless scrapers** – Hirist, Foundit, Shine, Monster, Glassdoor (now 8 total)
3. ✅ **Added 3 RSS sources** – Remotive Data, Remotive AI/ML, Stack Overflow (now 14 total)
4. ✅ **Increased headless limits** – Up to 200 jobs per scraper with pagination

**Result:** Should now get **700-1900+ jobs** per refresh (vs ~180 before)

---

## Current: 22 job sources (14 RSS + 8 Headless)

### RSS/HTTP Sources (14 total)

| # | Source            | Type        | Status        | Notes                          |
|---|-------------------|------------|---------------|--------------------------------|
| 1 | WeWorkRemotely    | RSS        | ✅ Working    | Returns jobs                   |
| 2 | Jobscollider      | RSS        | ✅ Working    | Lenient filter applied         |
| 3 | RemoteOK          | RSS        | ✅ Working    | Returns jobs (93 found)        |
| 4 | Remotive API      | API        | ✅ Working    | Lenient filter                 |
| 5 | Remotive RSS      | RSS        | ✅ Working    | Returns jobs (1 found)          |
| 6 | Remotive Data     | RSS        | ✅ **NEW**    | Data category feed             |
| 7 | Remotive AI/ML    | RSS        | ✅ **NEW**    | AI/ML category feed            |
| 8 | Wellfound         | RSS        | ✅ Working    | Multiple feeds                 |
| 9 | Indeed RSS        | RSS        | ✅ Working    |                                |
|10 | Remote.co         | RSS        | ✅ Working    |                                |
|11 | Jobspresso        | RSS        | ✅ Working    |                                |
|12 | Himalayas         | RSS        | ✅ Working    |                                |
|13 | Authentic Jobs    | RSS        | ✅ Working    |                                |
|14 | Stack Overflow    | RSS        | ✅ **NEW**    | Jobs RSS feed                  |

### Headless Scrapers (8 total)

| # | Source            | Type        | Status        | Notes                          |
|---|-------------------|------------|---------------|--------------------------------|
|15 | LinkedIn          | Headless   | ✅ **Fixed**  | Up to 200 jobs (was 30), pagination |
|16 | Indeed (browser)  | Headless   | ✅ **Fixed**  | Up to 200 jobs (was 30), pagination |
|17 | Naukri            | Headless   | ✅ **Fixed**  | Up to 200 jobs (was 30), pagination |
|18 | Hirist            | Headless   | ✅ **NEW**    | Up to 200 jobs, India-focused |
|19 | Foundit           | Headless   | ✅ **NEW**    | Up to 200 jobs, India-focused |
|20 | Shine             | Headless   | ✅ **NEW**    | Up to 200 jobs, India-focused |
|21 | Monster           | Headless   | ✅ **NEW**    | Up to 200 jobs, global         |
|22 | Glassdoor         | Headless   | ✅ **NEW**    | Up to 200 jobs, global         |

**Total: 22 sources** (14 RSS + 8 Headless)

---

## Plan to “complete the whole thing”

1. **RSS/HTTP (now)**  
   - Apply lenient date + query logic to all 11 RSS/API sources so every source can return jobs.  
   - Re-test `/refresh` and `/jobs` until multiple sources show up.

2. **Headless on Railway**  
   - Confirm `ENABLE_HEADLESS=1` is set.  
   - Check Railway logs for Playwright timeouts or blockages.  
   - If needed, run headless less often (e.g. only when explicitly requested) to avoid timeouts.

3. **Add remaining headless scrapers**  
   - Add Monster, Glassdoor, Hirist (and optionally more) so we reach 17–20 boards.  
   - Each new scraper: add function, add to `scrape_all()`, test locally then on Railway.

4. **Tests**  
   - Manual: hit `/debug`, `/refresh`, `/jobs` and check source counts.  
   - Optional: add a small script or GitHub Action that checks “at least N sources return &gt; 0 jobs”.

5. **UI integration (current: Vercel + frontend only)**  
   - **analytics-lab** and **playground-serverless** use the **Vercel** APIs only (no Railway for now):  
     - `GET /api/jobs-snapshot?q=...&days=...&limit=...` for listing (primary).  
     - `GET /api/jobs-cached?q=...` as fallback.  
     - `GET /api/jobs-refresh?q=...&days=...&location=...` for “Refresh jobs”.  
   - Frontend is configured via `window.JOB_PROXY_URL = 'https://playground-serveless.vercel.app'`.  
   - *(Optional later: point to Railway `GET /jobs` and `POST /refresh` if you deploy job-search-api there.)*

---

## When will it be “done”?

- **RSS/HTTP (11 sources)**: Done once lenient filtering is applied and deployed; then test.
- **Headless (3 live on Railway)**: Done after we verify they run and don’t always time out.
- **17–20 boards**: Done after we add the remaining headless scrapers and run a full test.
- **UI**: Done for current setup — both UIs use Vercel APIs (jobs-snapshot, jobs-cached, jobs-refresh). Railway is optional for later.

Next code steps: apply lenient filtering in the scraper (job-search-api). UI is already on Vercel + frontend.
