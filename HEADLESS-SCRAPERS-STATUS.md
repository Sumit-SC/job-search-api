# Headless Scrapers Status Report

**Date:** 2026-02-20  
**Base URL:** `https://job-search-api-production-5d5d.up.railway.app`  
**Test Result:** All 8 scrapers run but return 0 jobs

---

## ✅ Implemented Headless Scrapers (8 total)

All 8 headless scrapers are **implemented** in `app/scraper.py`:

| # | Scraper | Function | Status | Notes |
|---|---------|----------|--------|-------|
| 1 | **LinkedIn** | `scrape_linkedin()` | ✅ Code exists | Up to 200 jobs, pagination |
| 2 | **Indeed (browser)** | `scrape_indeed_headless()` | ✅ Code exists | Up to 200 jobs, pagination |
| 3 | **Naukri** | `scrape_naukri()` | ✅ Code exists | Up to 200 jobs, India-focused |
| 4 | **Hirist** | `scrape_hirist()` | ✅ Code exists | Up to 200 jobs, India-focused |
| 5 | **Foundit** | `scrape_foundit()` | ✅ Code exists | Up to 200 jobs, India-focused |
| 6 | **Shine** | `scrape_shine()` | ✅ Code exists | Up to 200 jobs, India-focused |
| 7 | **Monster** | `scrape_monster()` | ✅ Code exists | Up to 200 jobs, global |
| 8 | **Glassdoor** | `scrape_glassdoor()` | ✅ Code exists | Up to 200 jobs, global |

---

## ⚠️ Current Test Results

**Test:** `GET /debug/headless`  
**Result:** All 8 scrapers run successfully but return **0 jobs each**

```json
{
  "ok": true,
  "scrapers": {
    "linkedin": {"ok": true, "count": 0, "error": null},
    "indeed_headless": {"ok": true, "count": 0, "error": null},
    "naukri": {"ok": true, "count": 0, "error": null},
    "hirist": {"ok": true, "count": 0, "error": null},
    "foundit": {"ok": true, "count": 0, "error": null},
    "shine": {"ok": true, "count": 0, "error": null},
    "monster": {"ok": true, "count": 0, "error": null},
    "glassdoor": {"ok": true, "count": 0, "error": null}
  },
  "total_jobs": 0
}
```

---

## 🔍 Possible Reasons for 0 Jobs

### 1. **Site Structure Changed (Selectors Broken)**
- LinkedIn, Indeed, Naukri, etc. may have updated their HTML structure
- CSS selectors in the scrapers may no longer match
- **Fix:** Update selectors in scraper code

### 2. **Bot Detection / Blocking**
- Sites may be detecting Playwright/headless browsers
- LinkedIn especially known for blocking scrapers
- **Fix:** Add better user agents, cookies, or use proxies

### 3. **Date Filtering Too Strict**
- LinkedIn URL has hardcoded `f_TPR=r259200` (3 days)
- Debug endpoint uses `days=7`
- Date parsing might be failing
- **Fix:** Check date parsing logic

### 4. **No Jobs Match Query/Date**
- Query: "data analyst"
- Days: 7
- Maybe no jobs posted in last 7 days?
- **Fix:** Test with longer date range (30 days)

### 5. **JavaScript Not Loading**
- Sites might require JavaScript to load job listings
- Playwright might not be waiting long enough
- **Fix:** Increase wait times, use `networkidle` properly

---

## 🧪 Debugging Steps

### Step 1: Check Railway Logs
```bash
# Check Railway dashboard logs for:
# - Selector errors
# - Timeout errors
# - Network errors
# - Date parsing errors
```

### Step 2: Test Individual Scrapers
Modify `/debug/headless` to return more details:
- Raw HTML snippets
- Selector matches found
- Date values extracted
- Filter results

### Step 3: Test with Longer Date Range
```bash
# Test with 30 days instead of 7
curl "https://job-search-api-production-5d5d.up.railway.app/debug/headless?days=30"
```

### Step 4: Test Without Date Filter
Temporarily disable date filtering to see if jobs are found but filtered out.

### Step 5: Test Selectors Manually
1. Open site in browser (LinkedIn, Naukri, etc.)
2. Inspect job card HTML
3. Compare with selectors in scraper code
4. Update selectors if needed

---

## 📝 Code Issues Found

### LinkedIn Scraper (Line 734)
- **Issue:** Hardcoded `f_TPR=r259200` (3 days) in URL
- **Debug endpoint uses:** `days=7`
- **Fix:** Make URL parameter dynamic based on `days` parameter

### Date Parsing
- **Function:** `_parse_date()` (line 57)
- **Returns:** `None` if parsing fails
- **Filter:** `_within_days()` returns `True` if date is `None` (line 68)
- **Issue:** Jobs with unparseable dates pass the filter, but might fail elsewhere

### Selectors
- LinkedIn uses multiple fallback selectors (lines 751-763)
- Other scrapers might not have fallbacks
- **Fix:** Add fallback selectors to all scrapers

---

## 🚀 Recommended Fixes

### Priority 1: Add Better Logging
```python
# In each scraper, add logging:
logger.info(f"Found {len(jobs_data)} raw jobs from {source}")
logger.info(f"After date filter: {len([j for j in jobs_data if _within_days(...)])}")
logger.info(f"After query filter: {len([j for j in jobs_data if _matches_query(...)])}")
```

### Priority 2: Fix LinkedIn URL Parameter
```python
# Change line 734 from:
url = f"...&f_TPR=r259200&..."

# To:
days_seconds = days * 86400
url = f"...&f_TPR=r{days_seconds}&..."
```

### Priority 3: Test Without Filters
Temporarily disable date/query filters to see if jobs are found:
```python
# Comment out filters temporarily:
# if not _within_days(dt, days):
#     continue
# if not _matches_query(...):
#     continue
```

### Priority 4: Add Selector Debugging
```python
# Add to each scraper:
selectors_found = await page.evaluate("""
    () => {
        const selectors = [
            ".jobs-search__results-list",
            "[data-test-id='job-card']",
            // ... etc
        ];
        const found = [];
        for (const sel of selectors) {
            const count = document.querySelectorAll(sel).length;
            if (count > 0) found.push({selector: sel, count: count});
        }
        return found;
    }
""")
logger.info(f"Selectors found: {selectors_found}")
```

---

## 📊 Next Steps

1. ✅ **Verify scrapers are running** - DONE (all 8 run without errors)
2. ⏳ **Check Railway logs** - Need to check for selector/parsing errors
3. ⏳ **Test with longer date range** - Try `days=30`
4. ⏳ **Add better logging** - See what's happening inside scrapers
5. ⏳ **Update selectors** - If sites changed structure
6. ⏳ **Fix LinkedIn URL parameter** - Make it dynamic

---

## 📌 Notes

- **Wellfound is NOT headless** - It's an RSS source (RSS feed)
- **Indeed has TWO scrapers:**
  - `indeed_rss` - RSS feed (fast, working)
  - `indeed_headless` - Browser scraper (slow, returning 0 jobs)
- **All scrapers have 90-second timeout** in `/debug/headless`
- **Date filtering is lenient** - Returns `True` if date is `None`
- **Query filtering is very lenient** - Matches almost everything with data keywords

---

## 🔗 Related Files

- `app/scraper.py` - All scraper implementations
- `app/main.py` - `/debug/headless` endpoint (line 511)
- `SOURCES_STATUS.md` - Lists all 22 sources (14 RSS + 8 headless)
- `HEADLESS-SCRAPERS-TEST.md` - Testing guide
