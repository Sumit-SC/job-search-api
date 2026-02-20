# Railway API Parameters Guide

**Base URL:** `https://job-search-api-production-5d5d.up.railway.app`

---

## 📊 Limits & Pagination

### Default Limit: 100
- **Default:** `limit=100` (returns up to 100 jobs)
- **Maximum:** `limit=400` (can request up to 400 jobs per request)
- **Pagination:** Use `page` + `per_page` for better control

### Pagination Parameters

**Option 1: Using `limit` (Simple)**
```
GET /jobs?q=data%20analyst&days=7&limit=400
```
- Returns up to 400 jobs in one request
- No pagination info returned

**Option 2: Using `page` + `per_page` (Recommended)**
```
GET /jobs?q=data%20analyst&days=7&page=1&per_page=100
```
- Returns pagination info: `total`, `page`, `per_page`
- Better for large result sets
- `per_page` max: 100

**Example Response with Pagination:**
```json
{
  "ok": true,
  "count": 100,
  "jobs": [...],
  "total": 350,
  "page": 1,
  "per_page": 100
}
```

---

## 🔍 Search Parameters

### Basic Parameters

| Parameter | Type | Default | Description | Example |
|-----------|------|---------|-------------|---------|
| `q` | string | `null` | Free text query | `q=data%20analyst` |
| `days` | int | `3` | Max age of jobs (1-30) | `days=7` |
| `limit` | int | `100` | Max results (1-400) | `limit=400` |
| `source` | string | `null` | Filter by source | `source=linkedin` |

### Pagination Parameters

| Parameter | Type | Default | Description | Example |
|-----------|------|---------|-------------|---------|
| `page` | int | `null` | Page number (use with `per_page`) | `page=2` |
| `per_page` | int | `null` | Results per page (1-100) | `per_page=50` |

### Sorting Parameters

| Parameter | Type | Default | Options | Description |
|-----------|------|---------|---------|-------------|
| `sort` | string | `date` | `date`, `relevance`, `source` | Sort order |

### Filtering Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `yoe_min` | int | `null` | Minimum years of experience |
| `yoe_max` | int | `null` | Maximum years of experience (excludes 5+ if not specified) |
| `target_yoe` | int | `2` | Target YOE for match_score calculation (0-10) |

### Other Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `include_stats` | bool | `false` | Include system resource stats |

---

## 📝 Example Requests

### Get First 400 Jobs
```bash
curl "https://job-search-api-production-5d5d.up.railway.app/jobs?q=data%20analyst&days=7&limit=400"
```

### Get Page 1 (100 jobs per page)
```bash
curl "https://job-search-api-production-5d5d.up.railway.app/jobs?q=data%20analyst&days=7&page=1&per_page=100"
```

### Get Page 2
```bash
curl "https://job-search-api-production-5d5d.up.railway.app/jobs?q=data%20analyst&days=7&page=2&per_page=100"
```

### Filter by Source
```bash
curl "https://job-search-api-production-5d5d.up.railway.app/jobs?q=data%20analyst&source=linkedin&limit=400"
```

### Sort by Relevance
```bash
curl "https://job-search-api-production-5d5d.up.railway.app/jobs?q=data%20analyst&sort=relevance&limit=400"
```

### Filter by YOE
```bash
curl "https://job-search-api-production-5d5d.up.railway.app/jobs?q=data%20analyst&yoe_min=2&yoe_max=4&limit=400"
```

### Get All Jobs (Multiple Pages)
```bash
# Page 1
curl "https://job-search-api-production-5d5d.up.railway.app/jobs?q=data%20analyst&days=7&page=1&per_page=100"

# Page 2
curl "https://job-search-api-production-5d5d.up.railway.app/jobs?q=data%20analyst&days=7&page=2&per_page=100"

# Page 3
curl "https://job-search-api-production-5d5d.up.railway.app/jobs?q=data%20analyst&days=7&page=3&per_page=100"
```

---

## 🎯 Best Practices

### For Maximum Jobs (Up to 400)
```bash
GET /jobs?q=data%20analyst&days=7&limit=400
```

### For Pagination (Better for Large Results)
```bash
GET /jobs?q=data%20analyst&days=7&page=1&per_page=100
GET /jobs?q=data%20analyst&days=7&page=2&per_page=100
# ... continue until count < per_page
```

### For Efficient Search
1. **Use specific queries:** `q=data%20analyst` instead of `q=analyst`
2. **Filter by source:** `source=linkedin` to get only LinkedIn jobs
3. **Use date range:** `days=7` for recent jobs only
4. **Sort by relevance:** `sort=relevance` for best matches first
5. **Filter by YOE:** `yoe_min=2&yoe_max=4` for specific experience levels

---

## ⚠️ Important Notes

1. **Default Limit is 100** - Use `limit=400` to get more jobs
2. **Pagination Recommended** - For >100 jobs, use `page` + `per_page`
3. **Storage May Be Empty** - If `/jobs` returns empty, use `/refresh` first
4. **Max Limit is 400** - Cannot request more than 400 jobs per request
5. **Pagination Max:** `per_page` max is 100 (even though `limit` can be 400)

---

## 🔄 Refresh Endpoint

To scrape fresh jobs:
```bash
POST /refresh?q=data%20analyst&days=7&headless=0
```

Then fetch from `/jobs`:
```bash
GET /jobs?q=data%20analyst&days=7&limit=400
```
