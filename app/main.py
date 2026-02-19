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
    limit: int = Query(100, ge=1, le=400, description="Max results per response (used when not using page/per_page)"),
    source: Optional[str] = Query(None, description="Filter by source id"),
    page: Optional[int] = Query(None, ge=1, description="Page number for pagination (use with per_page)"),
    per_page: Optional[int] = Query(None, ge=1, le=100, description="Results per page (use with page)"),
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
    total = len(filtered)

    if page is not None and per_page is not None:
        start = (page - 1) * per_page
        limited = filtered[start : start + per_page]
        return JobsResponse(
            ok=True, count=len(limited), jobs=limited,
            total=total, page=page, per_page=per_page,
        )
    limited = filtered[:limit]
    return JobsResponse(ok=True, count=len(limited), jobs=limited)


@app.post("/refresh", response_model=JobsResponse)
async def refresh_jobs(
    q: Optional[str] = Query("data analyst", description="Default search query"),
    days: int = Query(3, ge=1, le=30),
    headless: Optional[bool] = Query(None, description="Include headless scrapers (default: from ENABLE_HEADLESS env). Use headless=0 for quick RSS-only refresh."),
) -> JobsResponse:
    enable_headless = headless if headless is not None else True
    jobs = await scrape_all(days=days, query=q, enable_headless=enable_headless)
    save_jobs(jobs)
    return JobsResponse(ok=True, count=len(jobs), jobs=jobs)


@app.get("/debug")
async def debug_scrapers() -> dict:
    """
    Debug endpoint: test all 11 RSS/HTTP scrapers. Fast; no headless.
    """
    from .scraper import (
        scrape_weworkremotely,
        scrape_jobscollider,
        scrape_remoteok,
        scrape_remotive_api,
        scrape_remotive_rss,
        scrape_wellfound,
        scrape_indeed_rss,
        scrape_remote_co,
        scrape_jobspresso,
        scrape_himalayas,
        scrape_authentic_jobs,
    )
    results = {}
    test_query = "data analyst"
    test_days = 7
    scrapers = {
        "weworkremotely": scrape_weworkremotely,
        "jobscollider": scrape_jobscollider,
        "remoteok": scrape_remoteok,
        "remotive_api": scrape_remotive_api,
        "remotive_rss": scrape_remotive_rss,
        "wellfound": scrape_wellfound,
        "indeed_rss": scrape_indeed_rss,
        "remote_co": scrape_remote_co,
        "jobspresso": scrape_jobspresso,
        "himalayas": scrape_himalayas,
        "authentic_jobs": scrape_authentic_jobs,
    }
    for name, scraper_func in scrapers.items():
        try:
            jobs = await scraper_func(days=test_days, query=test_query)
            results[name] = {"ok": True, "count": len(jobs), "error": None}
        except Exception as e:
            results[name] = {"ok": False, "count": 0, "error": str(e)}
    return {
        "ok": True,
        "scrapers": results,
        "total_jobs": sum(r["count"] for r in results.values()),
    }


@app.get("/debug/headless")
async def debug_headless_scrapers() -> dict:
    """
    Debug endpoint: test the 3 headless scrapers (LinkedIn, Indeed, Naukri).
    Requires Playwright + ENABLE_HEADLESS=1. Can be slow (up to ~90s).
    """
    import os
    from .scraper import (
        PLAYWRIGHT_AVAILABLE,
        scrape_linkedin,
        scrape_indeed_headless,
        scrape_naukri,
    )
    if not PLAYWRIGHT_AVAILABLE:
        return {
            "ok": False,
            "error": "Playwright not installed",
            "scrapers": {},
            "total_jobs": 0,
        }
    if os.getenv("ENABLE_HEADLESS", "1") != "1":
        return {
            "ok": True,
            "skipped": "ENABLE_HEADLESS is not 1",
            "scrapers": {},
            "total_jobs": 0,
        }
    from playwright.async_api import async_playwright
    import asyncio
    results = {}
    test_query = "data analyst"
    test_days = 7
    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            try:
                scrapers = [
                    ("linkedin", scrape_linkedin),
                    ("indeed_headless", scrape_indeed_headless),
                    ("naukri", scrape_naukri),
                ]
                for name, scraper_func in scrapers:
                    try:
                        jobs = await asyncio.wait_for(
                            scraper_func(days=test_days, query=test_query, browser=browser),
                            timeout=90.0,
                        )
                        results[name] = {"ok": True, "count": len(jobs), "error": None}
                    except asyncio.TimeoutError:
                        results[name] = {"ok": False, "count": 0, "error": "timeout (90s)"}
                    except Exception as e:
                        results[name] = {"ok": False, "count": 0, "error": str(e)}
            finally:
                await browser.close()
    except Exception as e:
        return {
            "ok": False,
            "error": str(e),
            "scrapers": results,
            "total_jobs": sum(r["count"] for r in results.values()),
        }
    return {
        "ok": True,
        "scrapers": results,
        "total_jobs": sum(r["count"] for r in results.values()),
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
