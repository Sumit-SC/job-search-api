# Headless Scrapers Test Report

**Date:** 2026-02-20  
**Base URL:** `https://job-search-api-production-5d5d.up.railway.app`

---

## ✅ Implemented Headless Scrapers (8 total)

According to the code, these 8 headless scrapers are implemented:

1. **LinkedIn** (`scrape_linkedin`)
2. **Indeed (browser)** (`scrape_indeed_headless`)
3. **Naukri** (`scrape_naukri`)
4. **Hirist** (`scrape_hirist`)
5. **Foundit** (`scrape_foundit`)
6. **Shine** (`scrape_shine`)
7. **Monster** (`scrape_monster`)
8. **Glassdoor** (`scrape_glassdoor`)

---

## 🧪 How to Test

### Option 1: Test All Headless Scrapers at Once

```bash
# Test all 8 headless scrapers (takes 2-5 minutes)
curl "https://job-search-api-production-5d5d.up.railway.app/debug/headless"
```

**Expected Response:**
```json
{
  "ok": true,
  "scrapers": {
    "linkedin": {"ok": true, "count": 15, "error": null},
    "indeed_headless": {"ok": true, "count": 20, "error": null},
    "naukri": {"ok": true, "count": 10, "error": null},
    "hirist": {"ok": true, "count": 5, "error": null},
    "foundit": {"ok": true, "count": 8, "error": null},
    "shine": {"ok": true, "count": 12, "error": null},
    "monster": {"ok": true, "count": 18, "error": null},
    "glassdoor": {"ok": true, "count": 25, "error": null}
  },
  "total_jobs": 113
}
```

### Option 2: Test via Refresh Endpoint

```bash
# Refresh with headless scrapers enabled (will take 2-5 minutes)
curl -X POST "https://job-search-api-production-5d5d.up.railway.app/refresh?q=data%20analyst&days=7&headless=1"
```

Then check `/jobs` to see which sources appear:
```bash
curl "https://job-search-api-production-5d5d.up.railway.app/jobs?limit=400"
```

Look for jobs with these sources:
- `linkedin`
- `indeed_headless`
- `naukri`
- `hirist`
- `foundit`
- `shine`
- `monster`
- `glassdoor`

---

## ⚠️ Common Issues

### 1. ENABLE_HEADLESS Not Set
**Symptom:** `/debug/headless` returns `{"skipped": "ENABLE_HEADLESS is not 1"}`

**Fix:** Set `ENABLE_HEADLESS=1` in Railway environment variables

### 2. Playwright Not Installed
**Symptom:** `/debug/headless` returns `{"error": "Playwright not installed"}`

**Fix:** Ensure Dockerfile includes Playwright installation (should be automatic)

### 3. Timeouts
**Symptom:** Some scrapers return `{"ok": false, "error": "Timeout"}`

**Possible Causes:**
- Site is blocking/scraping detection
- Network issues
- Site structure changed (selectors broken)

**Fix:** Check Railway logs for specific errors

### 4. No Jobs Returned
**Symptom:** Scraper returns `{"ok": true, "count": 0}`

**Possible Causes:**
- No jobs match query/date filter
- Site structure changed (selectors broken)
- Site requires authentication/cookies

**Fix:** Check Railway logs, verify site still works manually

---

## 📊 Testing Checklist

- [ ] Set `ENABLE_HEADLESS=1` in Railway
- [ ] Test `/debug/headless` endpoint (should show 8 scrapers)
- [ ] Check which scrapers return jobs vs errors
- [ ] Test `/refresh?headless=1` (should include headless jobs)
- [ ] Check `/jobs` to see which sources appear
- [ ] Review Railway logs for any errors

---

## 🔍 What to Look For

### Working Scraper
```json
{
  "linkedin": {
    "ok": true,
    "count": 15,
    "error": null
  }
}
```

### Failed Scraper (Timeout)
```json
{
  "linkedin": {
    "ok": false,
    "count": 0,
    "error": "Timeout after 90 seconds"
  }
}
```

### Failed Scraper (Error)
```json
{
  "linkedin": {
    "ok": false,
    "count": 0,
    "error": "Element not found: .job-card"
  }
}
```

---

## 📝 Notes

- **Wellfound is NOT headless** - it's an RSS source (RSS feed)
- **Indeed has TWO scrapers:**
  - `indeed_rss` - RSS feed (fast)
  - `indeed_headless` - Browser scraper (slow, more results)
- **All headless scrapers can fetch up to 200 jobs** (with pagination)
- **Each scraper has a 90-second timeout** in `/debug/headless`
- **Headless scraping is slow** - expect 2-5 minutes for all 8 scrapers

---

## 🚀 Next Steps

1. **Test `/debug/headless`** to see which scrapers work
2. **Check Railway logs** for any errors
3. **Update this document** with actual test results
4. **Fix broken scrapers** if any fail consistently
