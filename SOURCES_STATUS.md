# Job boards: status and plan

## Why only one source was returning data (until now)

1. **WeWorkRemotely** – We temporarily turned off date + query filters for debugging, so it returned 100 jobs.
2. **Other RSS sources** (jobscollider, remoteok, remotive, indeed_rss, etc.) – Still had strict filters:
   - Date: only last 3–7 days.
   - Query: required "data analyst" or specific keywords, so many entries were dropped.
3. **RemoteOK** – Had a bug comparing timezone-aware vs naive datetimes; that’s fixed.
4. **Headless (Playwright)** – LinkedIn, Indeed, Naukri are in the code and run when `ENABLE_HEADLESS=1`, but on Railway they may time out or be blocked by the sites. We only have 3 headless scrapers so far; the rest are still to be added.

So: we always had 11 RSS/HTTP sources + 3 headless in the pipeline; only one was configured to return data. The rest are being relaxed and fixed so all RSS/HTTP sources contribute.

---

## Target: 17–20 job boards

| # | Source            | Type        | Status        | Notes                          |
|---|-------------------|------------|---------------|--------------------------------|
| 1 | WeWorkRemotely    | RSS        | Working       | 100 jobs with lenient filter   |
| 2 | Jobscollider      | RSS        | Relaxing      | Lenient filter applied         |
| 3 | RemoteOK          | RSS        | Fixed         | Datetime fix applied           |
| 4 | Remotive          | API + RSS  | Relaxing      | Lenient filter                 |
| 5 | Wellfound         | RSS        | Relaxing      |                                |
| 6 | Indeed            | RSS        | Relaxing      |                                |
| 7 | Remote.co         | RSS        | Relaxing      |                                |
| 8 | Jobspresso        | RSS        | Relaxing      |                                |
| 9 | Himalayas         | RSS        | Relaxing      |                                |
|10 | Authentic Jobs    | RSS        | Relaxing      |                                |
|11 | (Remotive RSS x3) | RSS        | Same as 4     |                                |
|12 | LinkedIn          | Headless   | In code       | Needs ENABLE_HEADLESS=1, may block |
|13 | Indeed (browser)  | Headless   | In code       | Same                           |
|14 | Naukri            | Headless   | In code       | Same                           |
|15 | Monster           | Headless   | Not yet       | To add                         |
|16 | Glassdoor         | Headless   | Not yet       | To add                         |
|17 | Hirist            | Headless   | Not yet       | To add                         |
|18 | Others (optional) | Headless  | Not yet       | Foundit, TimesJobs, Shine, etc. |

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

5. **UI integration**  
   - Point **analytics-lab** (e.g. `jobs.js`) and **playground-serveless** job UI to the Railway API base URL:  
     `https://job-search-api-production-5d5d.up.railway.app`  
   - Use:  
     - `GET /jobs?days=7&limit=200` for listing.  
     - `POST /refresh?...` for “Refresh jobs” (optional, or run on a schedule).  
   - Keep existing filters (by source, date, query) in the UI; they’ll work on the combined list from all sources.

---

## When will it be “done”?

- **RSS/HTTP (11 sources)**: Done once lenient filtering is applied and deployed; then test.
- **Headless (3 live on Railway)**: Done after we verify they run and don’t always time out.
- **17–20 boards**: Done after we add the remaining headless scrapers and run a full test.
- **UI**: Done after we wire both UIs to the Railway API and verify listing + refresh.

Next code steps: apply lenient filtering everywhere in the scraper, then re-test and wire the UI to Railway.
