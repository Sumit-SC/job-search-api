# Headless Scraper Improvements

**Date:** 2026-02-19

---

## Changes Made

### ✅ Removed 30-Job Limit

**Before:** All headless scrapers (LinkedIn, Indeed, Naukri) had a hard limit of **30 jobs**.

**After:** 
- Default limit increased to **200 jobs** per scraper
- Can fetch up to **200 jobs** from each source
- Total potential: **600+ jobs** from headless scrapers alone

### ✅ Added Pagination & Scrolling

**LinkedIn:**
- Scrolls page up to 10 times to load lazy-loaded content
- Deduplicates jobs by URL
- Fetches all visible jobs before stopping

**Indeed:**
- Scrolls to load more jobs
- Clicks "Next" button to paginate (up to 10 pages)
- Deduplicates by URL

**Naukri:**
- Scrolls to load more jobs
- Clicks "Next" button to paginate (up to 10 pages)
- Deduplicates by URL

### ✅ Added `max_results` Parameter

All headless scrapers now accept `max_results` parameter:
- Default: `200`
- Can be increased if needed
- Prevents infinite loops while maximizing results

---

## Impact

### Before
- LinkedIn: Max 30 jobs
- Indeed: Max 30 jobs  
- Naukri: Max 30 jobs
- **Total: ~90 jobs max**

### After
- LinkedIn: Up to 200 jobs (with scrolling)
- Indeed: Up to 200 jobs (with pagination)
- Naukri: Up to 200 jobs (with pagination)
- **Total: Up to 600+ jobs**

**Combined with RSS scrapers (181 jobs found):**
- **Total potential: 780+ jobs** per refresh!

---

## Performance Notes

- **Scrolling/Pagination:** Adds ~2 seconds per scroll/page
- **Total time:** May take 30-60 seconds per scraper (vs 10-15s before)
- **Memory:** Slightly higher due to more jobs in memory
- **Deduplication:** Prevents duplicate jobs across pages

---

## Testing

After deploying, test with:

```bash
# Test headless scrapers (will take longer now)
curl "https://job-search-api-production-5d5d.up.railway.app/debug/headless"

# Refresh with headless enabled
curl -X POST "https://job-search-api-production-5d5d.up.railway.app/refresh?days=7&headless=1"
```

Expected results:
- LinkedIn: 50-200 jobs (depending on availability)
- Indeed: 50-200 jobs
- Naukri: 50-200 jobs

---

## Future Improvements

1. **Configurable max_results:** Add env var `MAX_HEADLESS_RESULTS` (default: 200)
2. **Parallel pagination:** Load multiple pages in parallel (faster)
3. **Smart stopping:** Stop early if no new jobs found for 2 pages
4. **Rate limiting:** Add delays between requests to avoid blocking
