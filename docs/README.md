# Job Search API — Documentation

This folder is the **docs/wiki** for the Job Search API. For interactive API reference, use the live docs (Swagger / ReDoc) served by the app.

---

## Quick links

| Resource | URL | Description |
|----------|-----|-------------|
| **Swagger UI** | `/docs` | Try endpoints and see **JSON-only** request/response examples |
| **ReDoc** | `/redoc` | Read-only API reference |
| **OpenAPI spec** | `/openapi.json` | Machine-readable API schema (JSON) |
| **Web UI** | `/ui/` | Core API, RSSJobs, JobSpy, Interview Prep, Monitor |

---

## API overview

All documented API endpoints return **JSON** (or RSS XML for `/jobs/rss` only). The Swagger docs at `/docs` show only safe JSON examples — no HTML or source code.

| Method | Path | Description |
|--------|------|-------------|
| GET | `/health` | Liveness check |
| GET | `/system` | System resources (CPU, RAM, disk) |
| GET | `/jobs` | List jobs (query, filters, pagination, sort) |
| GET | `/jobs/grouped-by-currency` | Jobs grouped by currency |
| GET | `/jobs/rss` | RSS feed (XML) |
| POST | `/refresh` | Scrape and refresh job store |
| GET | `/jobspy` | Jobs via python-jobspy (cached) |
| GET | `/rssjobs` | Proxy for rssjobs.app feeds (cached) |

Monitor and debug endpoints (e.g. `/api/monitor`, `/debug`) may require auth or are for internal use; see main [README](../README.md).

---

## Response format (JSON)

Successful job list responses look like:

```json
{
  "ok": true,
  "count": 2,
  "jobs": [
    {
      "id": "example-1",
      "title": "Data Analyst",
      "company": "Example Corp",
      "location": "Remote",
      "url": "https://example.com/job/1",
      "description": "Analyze data and build reports.",
      "source": "remotive",
      "date": "2025-02-15T12:00:00Z",
      "tags": ["data", "analytics"],
      "match_score": 85.0
    }
  ],
  "total": null,
  "page": null,
  "per_page": null,
  "system": null,
  "error": null
}
```

Error responses still use JSON, e.g. `{"ok": false, "count": 0, "jobs": [], "error": "message"}`.

---

## More

- **Run locally & deploy:** [README](../README.md)
- **Sources status:** [SOURCES_STATUS.md](../SOURCES_STATUS.md)
- **Workspace context:** [JOBS-SCRAPER.md](../JOBS-SCRAPER.md) (if present)
