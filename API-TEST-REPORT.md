# API Endpoint Test Report

**Date:** 2026-02-19  
**Base URL:** `https://job-search-api-production-5d5d.up.railway.app`

---

## Test Results

### ✅ Working Endpoints

| Endpoint | Status | Notes |
|----------|--------|-------|
| `GET /health` | ✅ **WORKING** | Returns `{"ok": true, "timestamp": "..."}` |

### ❌ Broken Endpoints

| Endpoint | Status | Issue |
|----------|--------|-------|
| `GET /debug` | ⚠️ **TIMEOUT** | Request timed out (likely slow or hanging) |
| `GET /jobs` | ❌ **500 ERROR** | "Internal Server Error" - likely missing `scoring.py` or validation error |
| `POST /refresh` | ❓ **NOT TESTED** | Need to test |
| `GET /debug/headless` | ❓ **NOT TESTED** | Need to test |

---

## Issues Found

### 1. **Critical: `/jobs` endpoint returns 500 Internal Server Error**

**Root Cause:** Likely one of:
- Missing `app/scoring.py` module (not deployed)
- Old jobs in storage don't have new fields (match_score, yoe_min, etc.) causing Pydantic validation errors
- Import error when loading scoring module

**Fix Needed:**
- Ensure `scoring.py` is included in deployment
- Add error handling for missing fields when loading old jobs
- Make new fields optional with defaults

### 2. **`/debug` endpoint times out**

**Possible Causes:**
- Scrapers are slow (normal, but should have timeout)
- One scraper is hanging
- Network issues

**Fix Needed:**
- Add timeout per scraper in `/debug`
- Add better error handling

---

## Missing Features (from PREFERENCES.md)

### ✅ Implemented
- [x] `sort` parameter (date, relevance, source)
- [x] `yoe_min` / `yoe_max` filtering
- [x] `match_score` calculation
- [x] Pagination (`page`, `per_page`)
- [x] Visa sponsorship detection
- [x] Salary/currency extraction
- [x] Skill-based matching

### ❌ Missing / Incomplete
- [ ] **Error handling** for old job schema (backward compatibility)
- [ ] **Group by currency** endpoint (for UI navigation)
- [ ] **Job type detection** (full_time, contract, etc.)
- [ ] **Location preference filtering** (Remote > Remote India > Indian cities)
- [ ] **Better error messages** (500 errors should return JSON with details)
- [ ] **OpenAPI/Swagger docs** (`/docs` endpoint)
- [ ] **Rate limiting** (optional)
- [ ] **Health check with more details** (storage status, scraper availability)

---

## Recommended Fixes (Priority Order)

### Priority 1: Fix `/jobs` 500 Error

1. **Add backward compatibility** for old job schema:
   ```python
   # In storage.py or models.py
   # When loading old jobs, set defaults for new fields
   ```

2. **Add try-catch** around scoring imports:
   ```python
   try:
       from .scoring import calculate_match_score
   except ImportError:
       # Fallback if scoring.py missing
   ```

3. **Add error handling** in `/jobs` endpoint:
   ```python
   try:
       # ... existing code
   except Exception as e:
       return {"ok": False, "error": str(e)}
   ```

### Priority 2: Fix `/debug` Timeout

1. Add per-scraper timeout (already has timeout in headless, but not RSS)
2. Add better error messages

### Priority 3: Add Missing Features

1. **Group by currency endpoint:**
   ```
   GET /jobs/grouped-by-currency?days=7
   Returns: {"INR": [...], "USD": [...], ...}
   ```

2. **Better error responses:**
   - Return JSON errors instead of 500 HTML
   - Include error details in response

3. **OpenAPI docs:**
   - FastAPI auto-generates `/docs` - verify it works

---

## Testing Checklist

- [ ] Fix `/jobs` 500 error
- [ ] Test `/refresh` endpoint
- [ ] Test `/debug` endpoint (with timeout)
- [ ] Test `/debug/headless` endpoint
- [ ] Test all query parameters on `/jobs`
- [ ] Test pagination
- [ ] Test sorting (date, relevance, source)
- [ ] Test YOE filtering
- [ ] Test backward compatibility (old jobs.json format)
- [ ] Verify `scoring.py` is deployed
- [ ] Check Railway logs for errors

---

## Next Steps

1. **Immediate:** Fix `/jobs` 500 error (backward compatibility + error handling)
2. **Short-term:** Add missing features (group by currency, better errors)
3. **Long-term:** Add more headless scrapers, improve match_score algorithm
