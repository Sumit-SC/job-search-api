# System Resource Monitoring

Monitor Railway VM resources (CPU, RAM, Disk) via API endpoints.

---

## Endpoints

### 1. `/system` - Detailed System Stats

**GET** `https://job-search-api-production-5d5d.up.railway.app/system`

Returns comprehensive system resource usage:

```json
{
  "ok": true,
  "timestamp": "2026-02-19T...",
  "system": {
    "cpu": {
      "percent": 15.5,
      "cores": 2,
      "process_cpu_percent": 2.3
    },
    "memory": {
      "total_mb": 1024.0,
      "used_mb": 512.5,
      "available_mb": 511.5,
      "percent": 50.0,
      "process_memory_mb": 125.3
    },
    "disk": {
      "path": "/app/data",
      "total_gb": 10.0,
      "used_gb": 2.5,
      "free_gb": 7.5,
      "percent": 25.0
    }
  },
  "railway": {
    "railway_environment": "production",
    "railway_service": "job-search-api",
    "port": "8000"
  }
}
```

**Use Cases:**
- Monitor VM resources before/after heavy operations
- Check if you're hitting memory limits
- Monitor disk usage (especially for `data/jobs.json`)
- Debug performance issues

---

### 2. Include Stats in API Responses

Add `?include_stats=true` to any endpoint to include resource stats:

**GET `/jobs?include_stats=true`**
```json
{
  "ok": true,
  "count": 10,
  "jobs": [...],
  "system": {
    "cpu_percent": 15.5,
    "memory_percent": 50.0,
    "memory_used_mb": 512.5,
    "memory_total_mb": 1024.0,
    "disk_percent": 25.0,
    "disk_used_gb": 2.5,
    "disk_total_gb": 10.0,
    "process_memory_mb": 125.3
  }
}
```

**POST `/refresh?include_stats=true`**
```json
{
  "ok": true,
  "count": 181,
  "jobs": [...],
  "system": {
    "cpu_percent": 45.2,
    "memory_percent": 65.0,
    ...
  }
}
```

**Use Cases:**
- See resource usage during job scraping (`/refresh`)
- Monitor load when fetching jobs (`/jobs`)
- Track resource usage over time

---

## Example Usage

### Monitor Before/After Refresh

```bash
# Before refresh
curl "https://job-search-api-production-5d5d.up.railway.app/system"

# Run refresh with stats
curl -X POST "https://job-search-api-production-5d5d.up.railway.app/refresh?days=7&headless=0&include_stats=true"

# After refresh
curl "https://job-search-api-production-5d5d.up.railway.app/system"
```

### Check Resources During Normal Operation

```bash
# Get jobs with resource stats
curl "https://job-search-api-production-5d5d.up.railway.app/jobs?days=7&limit=10&include_stats=true"
```

---

## What Each Metric Means

### CPU
- **cpu_percent**: Overall CPU usage (0-100%)
- **cores**: Number of CPU cores
- **process_cpu_percent**: This API process CPU usage

### Memory
- **memory_total_mb**: Total RAM available
- **memory_used_mb**: RAM currently used
- **memory_available_mb**: RAM available for use
- **memory_percent**: Memory usage percentage
- **process_memory_mb**: This API process memory usage

### Disk
- **disk_total_gb**: Total disk space
- **disk_used_gb**: Disk space used
- **disk_free_gb**: Disk space free
- **disk_percent**: Disk usage percentage
- **path**: Path being monitored (usually `/app/data`)

---

## Railway-Specific Info

The `/system` endpoint also returns Railway environment variables:
- `railway_environment`: Environment name (production, staging, etc.)
- `railway_service`: Service name
- `port`: Port the service is running on

---

## Monitoring Tips

1. **Before heavy operations**: Check `/system` before running `/refresh` with headless scrapers
2. **After operations**: Check `/system` to see resource impact
3. **Regular checks**: Use `include_stats=true` on `/jobs` to monitor during normal usage
4. **Alert thresholds**: Set up alerts if:
   - Memory > 80%
   - Disk > 90%
   - CPU consistently > 70%

---

## Railway Dashboard

Railway also provides built-in metrics in the dashboard:
- Go to your service → **Metrics** tab
- View CPU, Memory, Disk, Network graphs
- Historical data (up to 30 days)

The `/system` endpoint complements Railway's dashboard by providing programmatic access to the same metrics.
