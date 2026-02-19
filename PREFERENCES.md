# Confirmed job search preferences

**Source:** Questionnaire (confirmed). Use this as the single source of truth for filters, sort, roles, and API behaviour.

---

## 1. Primary roles (Tier 1)

- Data Analyst, Senior Data Analyst, Business Analyst, Product Analyst, BI Developer, Analytics Engineer, BI Analyst, Decision Scientist, Financial Analyst, Marketing Analyst (with data context), Operations Analyst.
- **Add:** broad **"analyst"** in search to fetch more results.

---

## 2. Secondary roles (Tier 2)

- Junior/Associate Data Scientist, Data Scientist, ML Engineer, Machine Learning Engineer.
- **Add:** **Junior/Associate ML Engineer**, **Junior/Associate Data Engineer**.

---

## 3. Exclude / focus (data domain only)

- **Focus:** Data domain only — **analyst** and **science** domains. Not heavy on pipeline building, deployment, or software development lifecycle.
- **Fresher/junior/intern:**  
  - **Data Engineer** with tags like associate, junior, or intern → **OK** to include.  
  - **Rest of roles:** Don’t populate if they’re fresher/intern/junior/associate unless they’re clearly in the data (analyst/science) domain.
- **Deprioritize / exclude:** Pure pipeline/DevOps, heavy SDE, backend-only, “5+ YOE only” (see Experience).

---

## 4. Experience (YOE)

- **Primary band:** 2–3 years (mid-level).
- **Also support:** 0–2 (junior/fresher) and 1–4 as **options** so the API can be called with different params to track/refresh (e.g. `yoe_min`, `yoe_max` or `experience_band`).
- **Hard rule:** **Avoid 5+ and above** — filter out or deprioritize jobs that ask for 5+ YOE (time waste, above current target).

---

## 5. Location priority

1. **Remote worldwide**
2. **Remote India**
3. **Indian cities** (order for “preferred cities”):  
   **Pune**, **Hyderabad** (pushed up for better results), Mumbai, **Thane**, **Navi Mumbai**, Bangalore, Chennai, Delhi/NCR.
4. **Foreign with visa sponsorship** — **open to all countries**. Include **any** job that says “sponsored visa available”, “visa sponsorship”, “relocation support”, or similar (keyword-based). Do **not** limit to a hardcoded list of countries (Japan, EU, US, etc.) — if the posting mentions visa sponsorship, include it regardless of country.

*(API: support a filter/flag like “visa_sponsorship” or detect from description; no country whitelist.)*

---

## 6. Mode of work

- **Primary:** Remote.
- **Open to:** Relocation to preferred city list (focus on top cities; Hyderabad after Pune for better results).
- **Ranking:** Remote first, then hybrid, then on-site.

---

## 7. Default query & role filter

- **Default search query:** Use **"analyst"** to fetch more results (broader).
- **UI:** Have a **filter / dropdown for different roles** so the user can narrow down easily (e.g. Analyst, Data Scientist, ML Engineer, Data Engineer).

---

## 8. Sort

- **Default / primary:** **Newest first** (by posted date) — to apply faster and get higher chances.
- **Also:** Relevance (role tier + location + YOE match).
- **API:** Support **manual toggle** — e.g. `sort=date` | `sort=relevance` | `sort=source` so the user can change sort in the UI.

---

## 9. Sources: RSS + data-job sites (Indian-friendly, remote-first)

- **Add as many RSS and proper data-job-related sites** as possible that:
  - **Allow Indian users** (India-based or hire remotely in India).
  - **Remote-first hiring** (explicitly remote or remote-friendly).
- **Already in list (keep):** LinkedIn, Naukri, Indeed, Glassdoor. **Priority to add:** Hirist, Wellfound, Foundit, Unstop, Shine.
- **RSS/API sources to include:** All current ones + any board that has data/analyst/BI/ML roles and is India- or remote-friendly (see RSS-AND-SOURCES.md in base repo; keep expanding the list). No hard limit — add as many relevant data-job sites as we can.

---

## 10. Domains, salary, job type

- **Domains:** No strong preference for now; need volume of jobs.
- **Salary / currency:**  
  - **Do not hard-set or remove any currency.** Be **open to all** currencies (INR, USD, GBP, SGD, EUR, AED, etc.).  
  - Provide an **option to group by currency** in the UI/API so the user can **navigate and filter** easily (e.g. “Group by currency” → list jobs under INR, then USD, then GBP, etc., or user picks order). This is for **easier navigation**, not for excluding currencies.
- **Job type:** Default to **Full-time**; **include all** (Contract, Part-time, Internship) with a filter so the user can narrow by job type.

---

## 11. Skill-based matching (don’t miss non–“data” roles)

- Many **software engineering / development** roles use **Python, SQL, visualization, ML modeling** etc. without explicitly saying “data analyst” or “data scientist” in the title. We may be **losing good opportunities** if we only match explicit “data” job postings.
- **Include roles** that mention these **skills** in the job description or requirements:
  - **Python**, **SQL**, **visualization** (Tableau, Power BI, Looker, etc.), **ML modeling**, **statistics**, **A/B testing**, **experimentation**, **analytics**, **reporting**, **dashboards**, **ETL**, **data pipeline** (when combined with analysis), etc.
- **Implementation:** Use keyword/skill matching (e.g. in `_matches_query` or a separate “skill match” score) so such roles are **surfaced** even when the title is “Software Engineer”, “Backend Engineer”, or “Product Engineer”. Can boost **match_score** when these skills appear. Full “apply or” / complex logic may be overhead — **simpler approach:** include jobs that hit a minimum skill-keyword threshold so we don’t miss great opportunities.

---

## 12. Apply links & match score (must-have)

- **Apply links:** API must return **actual links** to the **application page** and/or the **job posting page** so the user can go and apply. Every job must have a usable `url` (or `apply_url`) that points to the real post/apply page.
- **Match percentage / fit score:**  
  - Provide a **percentage fit** (e.g. 0–100%) so the user knows how well the job matches.  
  - Base it on: **YOE**, **skills**, **role**, **location**, and other preferences above.  
  - Expose in API (e.g. `match_score` or `fit_percent`) and show in UI.

---

## 13. Fetch vs response (pagination) limits

- **Fetching (scraper):** Do **not** cap total fetch at a low number (e.g. 50–100). Fetch from each source as much as it reasonably returns; merge and store a **large pool** so search is not limited.
- **Serving (API / UI):** Limit **per request** (e.g. `limit` or `per_page` 10–25 for UI, up to 400 if needed). Support **pagination** (`page` + `per_page` or `offset`/`limit`) so the frontend can request “page 2” without loading everything at once.

---

## API implementation notes (from preferences)

| Feature | Notes |
|--------|--------|
| `q` | Default "analyst"; support free text. |
| Pagination | `page` + `per_page` (or `limit`/`offset`); cap per_page (e.g. 10–25 for UI, max 400). Fetch/store has no low cap. |
| `sort` | `date` (newest first, default), `relevance`, `source`. |
| `yoe_min`, `yoe_max` or `experience_band` | Support 0–2, 1–4, 2–3; exclude/deprioritize 5+. |
| `location_preference` | Remote worldwide, Remote India, Indian cities (ordered), visa-sponsored regions. |
| `job_type` | full_time (default), contract, part_time, internship; include all, filter in UI. |
| Salary / currency | **Open to all currencies** (no hard-set list). Store/return currency code. Support **option to group by currency** in UI/API for navigation (user can order groups, e.g. INR then USD then others). |
| Visa sponsorship | **Any country.** Include jobs that mention “sponsored visa”, “visa sponsorship”, “relocation” etc. No country whitelist. |
| Skill-based match | Include roles with Python, SQL, visualization, ML modeling, etc. even if title isn’t “data”; use skill keywords to surface and optionally boost match_score. |
| `url` / `apply_url` | Always fetch and return real apply/posting link. |
| `match_score` / `fit_percent` | Compute from YOE, skills, role, location; return in each job. |
| Role filter (UI) | Filter by role type (Analyst, Data Scientist, ML Engineer, Data Engineer, etc.). |

---

*When you change preferences, update this file and any code that reads it (e.g. scraper filters, API sort logic).*
