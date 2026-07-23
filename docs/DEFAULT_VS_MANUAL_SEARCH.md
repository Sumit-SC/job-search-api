# Your position: default profile vs manual search

## Your goal (what you described)

- **By default**, the app should fetch jobs that match **your profile**:
  - **Location**: e.g. Remote, Remote India
  - **Experience level**: e.g. 2–3 YOE
  - **Roles**: e.g. Data Analyst, BI, Product Analyst (not pure Data Engineer)
  - **Mode of work**: Remote / Hybrid / On-site
  - Any other defaults (e.g. “data analyst” query, last 7 days)
- So on first load, you see **relevant results** without doing anything.
- **Manual search**: only when you turn on a “Manual search” (or similar) toggle do you:
  - Change query, location, experience, mode, etc.
  - Click “Search” (or similar) to **trigger a new fetch** with those filters.
- So: **default = one set of filters and one fetch**; **manual = you choose filters and then we fetch with those**.

---

## Current way of working

### Backend (job-search-api on Railway)

| What exists | What’s missing |
|-------------|-----------------|
| `GET /jobs?q=...&days=...&limit=...&source=...` | No `location`, `experience`, `work_mode`, `role` params |
| `POST /refresh?q=...&days=...` | Same: no location / experience / mode / role |
| Scrapers use hardcoded remote-focused feeds (e.g. “remote” in URL) | No way to pass “Remote India” or “2–3 YOE” or “Analyst only” into the scrape |

So today the backend does **not** apply your preferred location, experience level, role, or mode of work at fetch time.

### Frontend (analytics-lab `jobs.js`)

| What exists | What’s missing |
|-------------|-----------------|
| URL params: `q`, `days`, `limit`, `location` (and passed to API) | API is still **Vercel** (`/api/jobs-cached`, `/api/jobs-refresh`, `/api/jobs-snapshot`), **not Railway** |
| Client-side filters: Source, Match level, Status, Age, **Role** (Analyst / Scientist / Engineer / Associate) | These only filter **already loaded** jobs; they do **not** trigger a new fetch with new params |
| Defaults: `q=data analyst`, `days=3`, `location=remote` (from URL or hardcoded) | No single “default profile” (location + experience + role + mode) that is clearly separate from “manual” |
| Refresh button → calls refresh API then cached API | No “Manual search” toggle that switches to custom params and then “Search” to fetch |

So today:
- There is **no** “manual search” toggle; changing filters only narrows the current list.
- “Default” is effectively: whatever is in the URL (or code), and the backend doesn’t support your full profile (experience, role, mode).

---

## Future plan (to match your idea)

### 1) Backend (job-search-api)

- Add optional query params (for both `GET /jobs` and `POST /refresh`):
  - `location` – e.g. `remote`, `remote india`, `india`, `pune`
  - `experience_min`, `experience_max` – e.g. 2, 3 (years)
  - `work_mode` – e.g. `remote`, `hybrid`, `onsite`, or comma-separated
  - `role` – e.g. `analyst`, `scientist`, `engineer` (to prefer/filter by role)
- In `GET /jobs`: filter stored jobs by these (e.g. by `job.location`, and by parsing experience/role from title/description if needed).
- In `POST /refresh` / scrapers: where a portal supports it (e.g. LinkedIn `f_E=2,3`, Indeed `l=remote`), pass these through; otherwise filter after fetch.
- Keep existing `q`, `days`, `limit`, `source` behaviour.

### 2) Frontend (analytics-lab)

- **Default profile** (your position):
  - One place (e.g. “Default profile” or settings) where we store:
    - Query: e.g. `data analyst`
    - Location: e.g. `Remote` or `Remote India`
    - Experience: e.g. 2–3 years
    - Roles: e.g. Analyst / BI
    - Mode: e.g. Remote
    - Days: e.g. 7
  - On first load (and when “Use default profile” is on), call the **Railway** API with these params only — no manual inputs.
- **Manual search**:
  - A toggle (e.g. “Manual search” or “Custom search”) that, when **on**, shows:
    - Inputs: query, location, days, experience, mode, role (or dropdowns).
    - A “Search” button that **triggers a new fetch** (GET /jobs or POST /refresh + GET /jobs) with **these** params.
  - When the toggle is **off**, the app uses the default profile and does not show the manual inputs (or they are disabled).
- **Wire to Railway**:
  - Set `JOB_PROXY_URL` (or equivalent) to `https://job-search-api-production-5d5d.up.railway.app` so that:
    - Cached/refresh/snapshot requests go to Railway’s `GET /jobs` and `POST /refresh` instead of Vercel’s `/api/...`.

### 3) Flow summary

- **Default mode**: Load → use default profile → single fetch with profile params → show results → client-side filters (source, role, etc.) only narrow the list.
- **Manual mode**: User toggles “Manual search” → changes query/location/experience/mode/role → clicks “Search” → new fetch with those params → show results; client-side filters still apply on top.

---

## Current blockers

1. **UI not using Railway**  
   Frontend still calls Vercel `/api/jobs-cached`, `/api/jobs-refresh`, `/api/jobs-snapshot`. So even after we add params to Railway, the live UI won’t use them until we point the app to Railway.

2. **Backend doesn’t support your profile params**  
   No `location`, `experience`, `work_mode`, `role` in `GET /jobs` or `POST /refresh`. So we can’t “fetch by default” with your preferred location/experience/role/mode yet.

3. **No “manual search” in the UI**  
   There is no toggle for “use default profile” vs “manual search”, and no “Search” action that triggers a new fetch with custom params; filters only affect already-loaded jobs.

4. **No single “default profile”**  
   Defaults are scattered (URL params, hardcoded `data analyst`, `remote`). There’s no one place that clearly defines “my default location, experience, role, mode” and is used only when not in manual mode.

---

## To-do list (concise)

| # | Task | Where |
|---|------|--------|
| 1 | Point frontend to Railway (e.g. `JOB_PROXY_URL` or base URL) so jobs come from `GET /jobs` and `POST /refresh` | analytics-lab (and playground if needed) |
| 2 | Add `location`, `experience_min`, `experience_max`, `work_mode`, `role` to `GET /jobs` and `POST /refresh`; filter (and pass to scrapers where possible) | job-search-api |
| 3 | Define “default profile” in UI (query, location, experience, role, mode, days) and use it for the initial fetch when not in manual mode | analytics-lab jobs.js |
| 4 | Add “Manual search” toggle; when on, show query/location/experience/mode/role inputs and a “Search” button that triggers a new fetch with those params | analytics-lab jobs.js |
| 5 | (Optional) Persist default profile in localStorage and add “Edit default profile” in settings | analytics-lab |

---

## Short summary

- **Your position**: Default fetch = use my profile (location, experience, role, mode). Manual search = I change filters and then you run a new search with those filters.
- **Current**: Backend has no location/experience/role/mode; frontend uses Vercel and has no “default profile” vs “manual search” toggle; “filters” only filter the current list.
- **Plan**: Add profile params to the API, wire UI to Railway, add default profile + “Manual search” toggle and a “Search” that refetches with custom params.
- **Blockers**: UI not on Railway; API missing params; no toggle or default profile in UI.

Once we implement the to-do list above, behaviour will match your described position: default fetch with your profile, and manual search only when you toggle and click Search.
