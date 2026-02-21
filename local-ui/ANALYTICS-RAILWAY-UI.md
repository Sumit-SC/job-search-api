# Analytics for Railway Job Search UI

The Railway-hosted local UI (Core API, JobSpy, RSSJobs pages) sends visit and time-on-page events to the same analytics endpoint as the Playground. You can view **Jobs** traffic in the analytics dashboard by using the **Jobs** toggle.

---

## 1. Script: `analytics.js`

**Location:** `job-search-api/local-ui/analytics.js`

- Same behaviour as `analytics-lab/assets/js/analytics.js`: sends `site`, `event`, `path`, `sessionId`, device/fingerprint traits, and optional `durationMs` on unload.
- **Default site:** `railway-ui`
- **Default endpoint:** `https://events.colab.indevs.in/api/events`

**Usage in any HTML page:**

```html
<script src="analytics.js" defer></script>
<script>
  if (typeof initAnalyticsTracking === "function") {
    initAnalyticsTracking({
      site: "railway-ui",
      baseEvent: "core",   /* or "jobspy", "rssjobs", etc. */
      endpoint: "https://events.colab.indevs.in/api/events"
    });
  }
</script>
```

**Events sent:**

- `{baseEvent}_visit` — on page load
- `{baseEvent}_unload` — on beforeunload (with `durationMs`)

**Current pages:**

| Page        | baseEvent |
|------------|-----------|
| index.html (Core API) | `core`   |
| jobspy.html          | `jobspy` |
| rssjobs.html         | `rssjobs` |

**Debug:** Add `?analytics_debug=1` to the URL or set `localStorage.setItem("analytics_debug", "1")` to see console logs.

---

## 2. Worker dashboard: Jobs toggle

The Cloudflare Worker that ingests events lives in **analytics-lab**:  
`analytics-lab/assets/js/worker.analytics.js` (copy into your Worker in the dashboard).

Events are stored in D1 with a `site` column. To **track and view Jobs page (Railway UI) records**, add a **Jobs** toggle to the dashboard.

**Dashboard site filter (after update):**

- `?site=analytics-lab` — **Playground**
- `?site=portfolio` — **Portfolio**
- `?site=railway-ui` or `?site=jobs` — **Jobs** (Railway UI: Core API, JobSpy, RSSJobs)

### Worker code changes (paste into your Worker)

**1) Site filter** — replace the line that sets `siteFilter` with:

```js
const siteParam = url.searchParams.get("site");
const siteFilter =
  siteParam === "portfolio"
    ? "portfolio"
    : siteParam === "railway-ui" || siteParam === "jobs"
    ? "railway-ui"
    : "analytics-lab";
```

**2) Labels and toggle state** — replace the `currentSiteLabel` and `site*Active` block with:

```js
const currentSiteLabel =
  siteFilter === "portfolio"
    ? "Portfolio"
    : siteFilter === "railway-ui"
    ? "Jobs (Railway UI)"
    : "Playground";
const sitePlaygroundActive =
  siteFilter === "analytics-lab" ? " site-toggle-btn-active" : "";
const sitePortfolioActive =
  siteFilter === "portfolio" ? " site-toggle-btn-active" : "";
const siteJobsActive =
  siteFilter === "railway-ui" ? " site-toggle-btn-active" : "";
```

**3) Add the Jobs button** in the dashboard HTML, next to Playground and Portfolio:

```html
<div class="site-toggle">
  <a href="?site=analytics-lab" class="site-toggle-btn${sitePlaygroundActive}">Playground</a>
  <a href="?site=portfolio" class="site-toggle-btn${sitePortfolioActive}">Portfolio</a>
  <a href="?site=railway-ui" class="site-toggle-btn${siteJobsActive}">Jobs</a>
</div>
```

No D1 schema change: the Worker already stores `payload.site` as-is, so `railway-ui` events are saved once the Railway UI sends them. Use the **Jobs** button to view only those records.

---

## 3. Endpoint

Ensure your Worker is deployed and the ingest URL is:

`https://events.colab.indevs.in/api/events`  
(or one of the aliases: `/api/track`, `/events`, `/track`, `/ping`, `/log`)

The Railway UI uses this same endpoint; no extra config is needed beyond loading `analytics.js` and calling `initAnalyticsTracking` with `site: "railway-ui"` and the correct `baseEvent` per page.

---

## 4. Why analytics might not show Railway / job search

### Where to look in the dashboard

- **Railway UI (direct visits)**  
  When users open the Railway UI directly (e.g. `https://your-app.up.railway.app/ui/`), events are sent with `site: "railway-ui"`. In the dashboard, use the **Jobs** toggle (or `?site=railway-ui`) to see only those events.

- **Analytics-lab Jobs page with Railway backend**  
  When users use the Jobs page inside analytics-lab and select **Railway** as the API backend, the page still has `site: "analytics-lab"`. So those visits appear under **Playground**, not Jobs. To see that they used the Railway backend, look for events named **`jobs_search_railway`** (and optionally in Raw JSON: `meta.backend`, `meta.query`, `meta.days`).

- **Job search actions**  
  Each time jobs are fetched (initial load or Refresh), the Jobs page sends a `jobs_search_railway` or `jobs_search_vercel` event. So in **Playground** view, filter or scan the **Event** column for `jobs_search_railway` to confirm Railway job search usage.

### Checklist if nothing appears

1. **Dashboard filter** — For Railway UI traffic, open the dashboard and click **Jobs**. For analytics-lab + Railway backend usage, stay on **Playground** and look for `jobs_search_railway` events.
2. **Worker and URL** — The Worker must be deployed at the host you send to (e.g. `events.colab.indevs.in`). D1 must be bound as `ANALYTICS_DB`.
3. **Railway UI** — Confirm `/ui/analytics.js` returns 200 (e.g. open `https://your-app.up.railway.app/ui/analytics.js`). If the script fails to load, no events are sent.
4. **Ad-blockers / privacy** — `sendBeacon` or `fetch` to the events domain can be blocked. Test in an incognito window or with extensions disabled; use `?analytics_debug=1` on the page to see console logs.
5. **CORS** — The Worker allows any origin (`Access-Control-Allow-Origin: *` or echoed `Origin`). If you use a custom domain for the Worker, ensure it matches the URL used in `initAnalyticsTracking`.
