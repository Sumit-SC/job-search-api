# Datetime Comparison Fix

**Date:** 2026-02-20  
**Issue:** `can't compare offset-naive and offset-aware datetimes` error in `/jobs` endpoint

---

## 🔍 Problem

The error occurs when comparing:
- **Timezone-naive datetime** (`datetime.utcnow()`) - no timezone info
- **Timezone-aware datetime** (`job.date` with `tzinfo`) - has timezone info

Python doesn't allow comparing these two types directly.

### Root Cause

When jobs are loaded from JSON, Pydantic parses ISO datetime strings:
- `"2026-02-20T10:00:00Z"` → timezone-aware (UTC)
- `"2026-02-20T10:00:00+00:00"` → timezone-aware (UTC)
- `"2026-02-20T10:00:00"` → timezone-naive

But `datetime.utcnow()` creates timezone-naive datetimes, causing comparison errors.

---

## ✅ Solution

Added a `normalize_datetime()` helper function that:
1. Converts timezone-aware datetimes to UTC
2. Removes timezone info (makes it timezone-naive)
3. Returns timezone-naive datetime for safe comparison

### Code Added

```python
def normalize_datetime(dt: datetime | None) -> datetime | None:
    """
    Normalize datetime to timezone-naive UTC for safe comparison.
    Converts timezone-aware datetimes to UTC-naive.
    Returns None if input is None.
    """
    if dt is None:
        return None
    if dt.tzinfo is not None:
        # Convert timezone-aware to UTC, then remove timezone info
        return dt.astimezone(timezone.utc).replace(tzinfo=None)
    return dt
```

### Fixed Locations

1. **`/jobs` endpoint** (line 177-178):
   ```python
   job_date_normalized = normalize_datetime(job.date)
   if job_date_normalized and job_date_normalized < cutoff:
   ```

2. **Sorting** (lines 230-234):
   ```python
   filtered.sort(key=lambda j: (normalize_datetime(j.date) or datetime.min), reverse=True)
   ```

3. **`/jobs/grouped-by-currency` endpoint** (line 307-308):
   ```python
   job_date_normalized = normalize_datetime(job.date)
   if job_date_normalized and job_date_normalized < cutoff:
   ```

4. **`/jobs/rss` endpoint** (line 368-369, 379):
   ```python
   job_date_normalized = normalize_datetime(job.date)
   if job_date_normalized and job_date_normalized < cutoff:
   # ...
   filtered.sort(key=lambda j: (normalize_datetime(j.date) or datetime.min), reverse=True)
   ```

---

## 🧪 Testing

After the fix, the `/jobs` endpoint should:
- ✅ Work with timezone-aware datetimes from JSON
- ✅ Work with timezone-naive datetimes
- ✅ Handle `None` dates gracefully
- ✅ Sort correctly by date

### Test Command

```bash
curl "https://job-search-api-production-5d5d.up.railway.app/jobs?limit=10"
```

**Expected:** No datetime comparison errors, jobs returned successfully.

---

## 📝 Notes

- **Timezone-aware vs timezone-naive:**
  - **Aware:** `datetime(2026, 2, 20, 10, 0, 0, tzinfo=timezone.utc)` - has timezone info
  - **Naive:** `datetime(2026, 2, 20, 10, 0, 0)` - no timezone info

- **Why normalize to UTC-naive:**
  - `datetime.utcnow()` is timezone-naive
  - All comparisons use timezone-naive datetimes
  - Consistent behavior across the codebase

- **Similar fix exists in `scraper.py`:**
  - `_within_days()` function (line 66-74) already handles this correctly
  - Uses same normalization approach

---

## 🔗 Related Files

- `app/main.py` - Fixed datetime comparisons
- `app/scraper.py` - Already had correct datetime handling in `_within_days()`
- `app/storage.py` - Saves datetimes as ISO strings (may include timezone)
