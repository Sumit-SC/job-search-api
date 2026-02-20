# How Refresh & Fetch Logic Works

## Overview

The UI has **3 steps**:
1. **Step 1 – Refresh from sources** (scrapes new data from web)
2. **Step 2 – Fetch saved data** (loads from JSON store)
3. **Step 3 – Search & Filter** (client-side filtering of loaded data)

---

## Step 1: Refresh from Sources

### What Happens

When you click **"Step 1 – Refresh from sources"**, the UI calls:

```
POST /refresh?q=data analyst&days=3&headless=0&mode=rss
```

### How Scrapers Use the Parameters

#### 1. **Query Parameter (`q`)**

**Important:** The query is **NOT** sent to job board URLs. Instead:

- **RSS Scrapers** (WeWorkRemotely, Jobscollider, RemoteOK, etc.):
  - Fetch the **full RSS feed** (e.g., `https://weworkremotely.com/remote-jobs.rss`)
  - Get **all jobs** from that feed
  - Then **filter** each job by checking if the query words appear in `title` or `description`
  - Uses a **very lenient matching** function (`_matches_query()`):
    - Generic queries like "data analyst" → matches almost everything with data-related keywords
    - Always includes jobs with keywords: "data", "analyst", "analytics", "python", "sql", etc.
    - For specific queries → matches if any query word appears in title/description

- **Headless Scrapers** (LinkedIn, Indeed, Naukri, etc.):
  - Some **DO** use query in the URL (e.g., LinkedIn search URL includes query)
  - Others fetch a category page and filter client-side

- **JobSpy** (if `USE_JOBSPY=1`):
  - Uses query directly: `scrape_jobs(site_name=["indeed", "linkedin"], search_term="data analyst", ...)`
  - This **does** search on the actual job boards

#### 2. **Days Parameter (`days`)**

- Filters jobs by **publication date**
- Only keeps jobs where `job.date >= (now - days)`
- Applied **after** fetching the feed/HTML

### Example Flow

```
User clicks "Refresh" with query="data analyst", days=3

1. Scraper calls: GET https://weworkremotely.com/remote-jobs.rss
   → Gets 100 jobs from feed

2. For each job:
   - Check if posted_date >= (today - 3 days) → Keep if yes
   - Check if "data analyst" matches title/description → Keep if yes
   → Result: Maybe 20 jobs match both criteria

3. Repeat for all 14 RSS scrapers + 8 headless scrapers (if enabled)

4. All matching jobs are saved to data/jobs.json
```

---

## Step 2: Fetch Saved Data

### What Happens

When you click **"Step 2 – Fetch saved data"**, the UI calls:

```
GET /jobs?days=7&limit=200&sort=date
```

### How It Works

- **Reads** from `data/jobs.json` (the file saved by Step 1)
- **Filters** by:
  - `days`: Only jobs posted in last N days
  - `limit`: Max number of jobs to return
  - `sort`: Sort order (date, relevance, source, etc.)
- **Does NOT** run any scrapers
- **Does NOT** use the "Refresh query" - that was only used during Step 1

### Important Distinction

- **Step 1 (Refresh)** = Scrapes from web → Saves to JSON
- **Step 2 (Fetch)** = Reads from JSON → Loads into UI memory

---

## Step 3: Search & Filter

### What Happens

When you click **"Search Jobs"**, the UI:

- **Does NOT** hit the API
- Filters `allJobs[]` (the array loaded in Step 2) **client-side**
- Uses filters like:
  - Query text (searches title/company/location/description)
  - Location contains
  - Remote only
  - Source checkboxes
  - YOE range
  - Currency
  - Sort order

---

## Why Two Different "Query" Fields?

### Refresh Query (Step 1)
- **Purpose:** Filter jobs **during scraping** (before saving)
- **Scope:** Applied to **all scrapers** (RSS + headless)
- **Behavior:** Very lenient matching (includes data-related jobs even if query doesn't match exactly)

### Search Query (Step 3)
- **Purpose:** Filter jobs **after loading** (client-side)
- **Scope:** Applied to **already-loaded** jobs in `allJobs[]`
- **Behavior:** Exact substring matching (must contain query text)

---

## Recommendations

### Current Behavior (Works, but can be confusing)

- Refresh query filters during scraping → saves fewer jobs
- Fetch loads saved jobs → you can't change the query here
- Search filters loaded jobs → you can refine further

### Potential Improvement

You could add a **"Manual Search"** mode where:

1. **Refresh without query** → Scrape ALL jobs (no query filter)
2. **Save everything** to JSON
3. **Fetch with query** → Use `/jobs?q=...` to filter at fetch time
4. **Search** → Further refine client-side

This would give you more flexibility: scrape once, filter multiple times.

---

## Summary

| Step | Action | Query Used? | Days Used? | Where Applied |
|------|--------|-------------|------------|---------------|
| **Step 1: Refresh** | Scrapes from web | ✅ Yes (filters during scraping) | ✅ Yes (filters by date) | Server-side (scraper functions) |
| **Step 2: Fetch** | Loads from JSON | ❌ No (uses `/jobs` endpoint filters) | ✅ Yes (filters by date) | Server-side (`/jobs` endpoint) |
| **Step 3: Search** | Filters loaded data | ✅ Yes (client-side text search) | ✅ Yes (client-side date filter) | Client-side (JavaScript) |

The **Refresh query** is used **once** during scraping. After that, you can only filter what was saved.
