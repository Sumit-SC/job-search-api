from __future__ import annotations

from datetime import datetime, timedelta
from typing import List, Optional

from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware

from .models import Job, JobsResponse
from .scraper import scrape_all
from .storage import load_jobs, save_jobs


app = FastAPI(title="Jobs Scraper API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health() -> dict:
    return {"ok": True, "timestamp": datetime.utcnow().isoformat() + "Z"}


@app.get("/jobs", response_model=JobsResponse)
async def get_jobs(
    q: Optional[str] = Query(None, description="Free text query, e.g. 'data analyst'"),
    days: int = Query(3, ge=1, le=30, description="Max age of jobs in days"),
    limit: int = Query(100, ge=1, le=400),
    source: Optional[str] = Query(None, description="Filter by source id"),
) -> JobsResponse:
    all_jobs: List[Job] = load_jobs()
    if not all_jobs:
        return JobsResponse(ok=True, count=0, jobs=[])

    cutoff = datetime.utcnow() - timedelta(days=days)
    filtered: List[Job] = []
    q_lower = q.lower() if q else None

    for job in all_jobs:
        if job.date and job.date < cutoff:
            continue
        if source and job.source != source:
            continue
        if q_lower:
            text = f"{job.title} {job.company} {job.location} {job.description}".lower()
            if q_lower not in text:
                continue
        filtered.append(job)

    filtered.sort(key=lambda j: (j.date or datetime.min), reverse=True)
    limited = filtered[:limit]

    return JobsResponse(ok=True, count=len(limited), jobs=limited)


@app.post("/refresh", response_model=JobsResponse)
async def refresh_jobs(
    q: Optional[str] = Query("data analyst", description="Default search query"),
    days: int = Query(3, ge=1, le=30),
) -> JobsResponse:
    jobs = await scrape_all(days=days, query=q)
    save_jobs(jobs)
    return JobsResponse(ok=True, count=len(jobs), jobs=jobs)


@app.get("/debug")
async def debug_scrapers() -> dict:
    """
    Debug endpoint to test individual scrapers and see what's working.
    """
    import asyncio
    from .scraper import (
        scrape_weworkremotely,
        scrape_jobscollider,
        scrape_remoteok,
        scrape_remotive_api,
        scrape_indeed_rss,
    )
    
    results = {}
    test_query = "data analyst"
    test_days = 7  # Use 7 days to get more results
    
    # Test a few key scrapers
    scrapers = {
        "weworkremotely": scrape_weworkremotely,
        "jobscollider": scrape_jobscollider,
        "remoteok": scrape_remoteok,
        "remotive_api": scrape_remotive_api,
        "indeed_rss": scrape_indeed_rss,
    }
    
    for name, scraper_func in scrapers.items():
        try:
            jobs = await scraper_func(days=test_days, query=test_query)
            results[name] = {
                "ok": True,
                "count": len(jobs),
                "error": None,
            }
        except Exception as e:
            results[name] = {
                "ok": False,
                "count": 0,
                "error": str(e),
            }
    
    return {
        "ok": True,
        "scrapers": results,
        "total_jobs": sum(r["count"] for r in results.values()),
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
