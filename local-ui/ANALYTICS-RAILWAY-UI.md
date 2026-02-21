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
