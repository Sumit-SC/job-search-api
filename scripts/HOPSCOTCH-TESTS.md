# Testing Railway API with Hopscotch / Postman / Insomnia

**Base URL:** `https://job-search-api-production-5d5d.up.railway.app`

---

## Quick Setup in Hopscotch

1. **Create a new collection** called "Job Search API"
2. **Set base URL variable:** `{{baseUrl}}` = `https://job-search-api-production-5d5d.up.railway.app`
3. **Or** just use the full URL in each request

---

## Test Requests (in order)

### 1. Health Check
**Method:** `GET`  
**URL:** `https://job-search-api-production-5d5d.up.railway.app/health`  
**Expected Response:**
```json
{
  "ok": true,
  "timestamp": "2026-02-18T..."
}
```

---

### 2. Debug RSS Scrapers
**Method:** `GET`  
**URL:** `https://job-search-api-production-5d5d.up.railway.app/debug`  
**Expected Response:**
```json
{
  "ok": true,
  "scrapers": {
    "weworkremotely": {"ok": true, "count": 5, "error": null},
    "jobscollider": {"ok": true, "count": 3, "error": null},
    ...
  },
  "total_jobs": 45
}
```
**Note:** This tests all 11 RSS/HTTP scrapers. Takes ~5-15 seconds.

---

### 3. Refresh Jobs (RSS-only, fast)
**Method:** `POST`  
**URL:** `https://job-search-api-production-5d5d.up.railway.app/refresh?days=7&headless=0`  
**Query Params:**
- `days` = `7`
- `headless` = `0` (RSS-only, faster)

**Expected Response:**
```json
{
  "ok": true,
  "count": 50,
  "jobs": [...]
}
```
**Note:** This scrapes jobs and saves them. Takes ~10-30 seconds.

---

### 4. Get Jobs (basic)
**Method:** `GET`  
**URL:** `https://job-search-api-production-5d5d.up.railway.app/jobs?days=7&limit=5`  
**Query Params:**
- `days` = `7`
- `limit` = `5`

**Expected Response:**
```json
{
  "ok": true,
  "count": 5,
  "jobs": [
    {
      "id": "...",
      "title": "Data Analyst",
      "company": "...",
      "location": "Remote",
      "url": "https://...",
      "source": "weworkremotely",
      "match_score": 75.5,
      "yoe_min": 2,
      "yoe_max": 3,
      "currency": "USD",
      "visa_sponsorship": false,
      ...
    }
  ]
}
```

---

### 5. Get Jobs (sorted by relevance)
**Method:** `GET`  
**URL:** `https://job-search-api-production-5d5d.up.railway.app/jobs?days=7&limit=5&sort=relevance`  
**Query Params:**
- `days` = `7`
- `limit` = `5`
- `sort` = `relevance` (sorts by match_score)

**Expected Response:** Same as #4, but jobs sorted by `match_score` (highest first).

---

### 6. Get Jobs (filtered by YOE)
**Method:** `GET`  
**URL:** `https://job-search-api-production-5d5d.up.railway.app/jobs?days=7&limit=5&yoe_min=1&yoe_max=3`  
**Query Params:**
- `days` = `7`
- `limit` = `5`
- `yoe_min` = `1`
- `yoe_max` = `3`
- `target_yoe` = `2` (optional, default: 2)

**Expected Response:** Only jobs matching 1-3 years of experience.

---

### 7. Get Jobs (with pagination)
**Method:** `GET`  
**URL:** `https://job-search-api-production-5d5d.up.railway.app/jobs?days=7&page=1&per_page=10`  
**Query Params:**
- `days` = `7`
- `page` = `1`
- `per_page` = `10`

**Expected Response:**
```json
{
  "ok": true,
  "count": 10,
  "total": 50,
  "page": 1,
  "per_page": 10,
  "jobs": [...]
}
```

---

### 8. Get Jobs (filtered by source)
**Method:** `GET`  
**URL:** `https://job-search-api-production-5d5d.up.railway.app/jobs?days=7&limit=10&source=weworkremotely`  
**Query Params:**
- `days` = `7`
- `limit` = `10`
- `source` = `weworkremotely`

**Expected Response:** Only jobs from WeWorkRemotely.

---

### 9. Get Jobs (with search query)
**Method:** `GET`  
**URL:** `https://job-search-api-production-5d5d.up.railway.app/jobs?days=7&limit=10&q=data%20analyst`  
**Query Params:**
- `days` = `7`
- `limit` = `10`
- `q` = `data analyst`

**Expected Response:** Jobs matching "data analyst" in title/description.

---

### 10. Debug Headless Scrapers (optional, slow)
**Method:** `GET`  
**URL:** `https://job-search-api-production-5d5d.up.railway.app/debug/headless`  
**Timeout:** Set to 120 seconds (this is slow!)

**Expected Response:**
```json
{
  "ok": true,
  "scrapers": {
    "linkedin": {"ok": true, "count": 5, "error": null},
    "indeed_headless": {"ok": true, "count": 3, "error": null},
    "naukri": {"ok": true, "count": 2, "error": null}
  },
  "total_jobs": 10
}
```
**Note:** Only works if `ENABLE_HEADLESS=1` is set in Railway. Takes ~60-90 seconds.

---

## Hopscotch Collection JSON (import this)

Save this as `job-search-api-hopscotch.json` and import into Hopscotch:

```json
{
  "name": "Job Search API - Railway",
  "baseUrl": "https://job-search-api-production-5d5d.up.railway.app",
  "requests": [
    {
      "name": "1. Health Check",
      "method": "GET",
      "url": "{{baseUrl}}/health"
    },
    {
      "name": "2. Debug RSS Scrapers",
      "method": "GET",
      "url": "{{baseUrl}}/debug"
    },
    {
      "name": "3. Refresh Jobs (RSS-only)",
      "method": "POST",
      "url": "{{baseUrl}}/refresh?days=7&headless=0"
    },
    {
      "name": "4. Get Jobs (basic)",
      "method": "GET",
      "url": "{{baseUrl}}/jobs?days=7&limit=5"
    },
    {
      "name": "5. Get Jobs (sort by relevance)",
      "method": "GET",
      "url": "{{baseUrl}}/jobs?days=7&limit=5&sort=relevance"
    },
    {
      "name": "6. Get Jobs (filter YOE 1-3)",
      "method": "GET",
      "url": "{{baseUrl}}/jobs?days=7&limit=5&yoe_min=1&yoe_max=3"
    },
    {
      "name": "7. Get Jobs (pagination)",
      "method": "GET",
      "url": "{{baseUrl}}/jobs?days=7&page=1&per_page=10"
    },
    {
      "name": "8. Get Jobs (filter by source)",
      "method": "GET",
      "url": "{{baseUrl}}/jobs?days=7&limit=10&source=weworkremotely"
    },
    {
      "name": "9. Get Jobs (search query)",
      "method": "GET",
      "url": "{{baseUrl}}/jobs?days=7&limit=10&q=data%20analyst"
    },
    {
      "name": "10. Debug Headless (slow)",
      "method": "GET",
      "url": "{{baseUrl}}/debug/headless",
      "timeout": 120000
    }
  ]
}
```

---

## Testing Workflow

1. **Start with Health Check** → Verify API is up
2. **Run Debug RSS** → See which scrapers work
3. **Run Refresh** → Scrape and save jobs (this populates the database)
4. **Run Get Jobs** → Verify jobs are returned with `match_score`, `yoe_min`, etc.
5. **Test sorting/filtering** → Try different query params

---

## Common Issues

- **0 jobs returned:** Run `/refresh` first to scrape jobs
- **Timeout on headless:** Normal if `ENABLE_HEADLESS=0` or Playwright not installed
- **CORS errors:** Shouldn't happen (CORS is open), but check if calling from browser
- **502/503:** Railway service might be sleeping; wait a few seconds and retry

---

## Tips for Hopscotch

- **Save responses:** Right-click → Save Response to compare before/after
- **Use variables:** Set `baseUrl` as a variable so you can switch between local/Railway
- **Set timeouts:** For `/refresh` and `/debug/headless`, set timeout to 120 seconds
- **Export collection:** Save your collection so you can reuse it
