# Custom Scrapers Testing

Comprehensive dry-run tests for **22 job sources** (15 RSS + 7 JSON APIs) focused on remote data/analyst roles.

## Sources

### RSS Feeds (15)

| Source | URL | Status |
|--------|-----|--------|
| WeWorkRemotely | `/remote-jobs.rss` | Working |
| Jobscollider | `/remote-jobs.rss` | Working |
| Jobscollider (Data) | `/remote-data-jobs.rss` | Working |
| RemoteOK | `/remote-jobs.rss` | Working |
| Remotive (Data) | `/remote-jobs/feed/data` | Empty (timing) |
| Remotive (AI/ML) | `/remote-jobs/feed/ai-ml` | Working |
| Jobspresso | `/remote-jobs/feed/` | Empty (timing) |
| Authentic Jobs | `/rss/` | Working |
| HN Jobs (hnrss) | `/jobs` | Working |
| **rssjobs.app** | `/feeds?keywords=analyst&location=remote` | Working (10K+) |
| **Jobicy RSS** | `/jobs-rss-feed` | 403 (use API) |
| **RealWorkFromAnywhere** | `/rss.xml` | Working (229) |
| Himalayas RSS | `/jobs/feed` | 403 (use API) |
| Remote.co | `/remote-jobs/feed/` | Timeout |
| Wellfound | `/jobs.rss?keywords=...&remote=true` | 403 |

### JSON APIs (7)

| Source | Endpoint | Status |
|--------|----------|--------|
| Remotive API | `GET /api/remote-jobs?category=data` | Working |
| Jobicy API | `GET /api/v2/remote-jobs?tag=data+analyst` | Working |
| Arbeitnow API | `GET /api/job-board-api` | Working |
| Himalayas API | `GET /jobs/api?q=analyst` | Working |
| **hiring.cafe** | `GET /api/search-jobs?searchQuery=...&workplaceTypes=Remote` | Working (155) |
| **WorkingNomads API** | `GET /api/exposed_jobs/` | Working (28) |
| **Jobscollider API** | `GET /api/search-jobs?title=data+analyst` | Working (100) |

## Setup

```bash
python -m venv .venv
.venv\Scripts\activate     # Windows
pip install -r requirements.txt
```

## Run

- **Notebook:** Open `scraper_test.ipynb`, select `.venv` kernel, run cells
- **Script:** `.venv\Scripts\python dry_run.py`

## Last test results

- **22 sources tested, 14 working**
- **10,869 total jobs** across all sources
- Top: rssjobs.app (10K+), RealWorkFromAnywhere (229), hiring.cafe (155)
