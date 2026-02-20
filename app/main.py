from __future__ import annotations

import logging
import sys
from datetime import datetime, timedelta
from typing import List, Optional

import html
from fastapi import FastAPI, Query, Request, Response
from fastapi.middleware.cors import CORSMiddleware

from .models import Job, JobsResponse, GroupedByCurrencyResponse
from .scraper import scrape_all
from .storage import load_jobs, save_jobs

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

# Import scoring with fallback
try:
    from .scoring import calculate_match_score, enhance_job_with_metadata
except ImportError:
    # Fallback if scoring.py is missing
    def calculate_match_score(*args, **kwargs):
        return 50.0  # Default neutral score
    def enhance_job_with_metadata(*args, **kwargs):
        return {}


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


@app.get("/system")
async def system_resources() -> dict:
    """
    Get system resource usage (CPU, RAM, Disk).
    Useful for monitoring Railway VM resources.
    """
    try:
        import psutil
        import os
        from pathlib import Path
        
        # CPU
        cpu_percent = psutil.cpu_percent(interval=1)
        cpu_count = psutil.cpu_count()
        
        # Memory
        memory = psutil.virtual_memory()
        memory_total_mb = memory.total / (1024 * 1024)
        memory_used_mb = memory.used / (1024 * 1024)
        memory_percent = memory.percent
        memory_available_mb = memory.available / (1024 * 1024)
        
        # Disk (check data directory if set, else root)
        data_dir = os.environ.get("JOBS_SCRAPER_DATA_DIR", "data")
        disk_path = Path(data_dir)
        if not disk_path.exists():
            disk_path = Path("/")
        disk = psutil.disk_usage(str(disk_path))
        disk_total_gb = disk.total / (1024 * 1024 * 1024)
        disk_used_gb = disk.used / (1024 * 1024 * 1024)
        disk_free_gb = disk.free / (1024 * 1024 * 1024)
        disk_percent = disk.percent
        
        # Process info
        process = psutil.Process()
        process_memory_mb = process.memory_info().rss / (1024 * 1024)
        process_cpu_percent = process.cpu_percent(interval=0.1)
        
        # Railway environment info
        railway_env = {
            "railway_environment": os.environ.get("RAILWAY_ENVIRONMENT"),
            "railway_service": os.environ.get("RAILWAY_SERVICE_NAME"),
            "port": os.environ.get("PORT", "8000"),
        }
        
        return {
            "ok": True,
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "system": {
                "cpu": {
                    "percent": round(cpu_percent, 2),
                    "cores": cpu_count,
                    "process_cpu_percent": round(process_cpu_percent, 2),
                },
                "memory": {
                    "total_mb": round(memory_total_mb, 2),
                    "used_mb": round(memory_used_mb, 2),
                    "available_mb": round(memory_available_mb, 2),
                    "percent": round(memory_percent, 2),
                    "process_memory_mb": round(process_memory_mb, 2),
                },
                "disk": {
                    "path": str(disk_path),
                    "total_gb": round(disk_total_gb, 2),
                    "used_gb": round(disk_used_gb, 2),
                    "free_gb": round(disk_free_gb, 2),
                    "percent": round(disk_percent, 2),
                },
            },
            "railway": railway_env,
        }
    except ImportError:
        return {
            "ok": False,
            "error": "psutil not installed",
            "timestamp": datetime.utcnow().isoformat() + "Z",
        }
    except Exception as e:
        return {
            "ok": False,
            "error": str(e),
            "timestamp": datetime.utcnow().isoformat() + "Z",
        }


@app.get("/jobs", response_model=JobsResponse)
async def get_jobs(
    q: Optional[str] = Query(None, description="Free text query, e.g. 'data analyst'"),
    days: int = Query(3, ge=1, le=30, description="Max age of jobs in days"),
    limit: int = Query(100, ge=1, le=400, description="Max results per response (used when not using page/per_page)"),
    source: Optional[str] = Query(None, description="Filter by source id"),
    page: Optional[int] = Query(None, ge=1, description="Page number for pagination (use with per_page)"),
    per_page: Optional[int] = Query(None, ge=1, le=100, description="Results per page (use with page)"),
    sort: Optional[str] = Query("date", description="Sort order: 'date' (newest first), 'relevance' (match_score), 'source'"),
    yoe_min: Optional[int] = Query(None, ge=0, description="Filter: minimum years of experience"),
    yoe_max: Optional[int] = Query(None, ge=0, description="Filter: maximum years of experience (excludes 5+ if not specified)"),
    target_yoe: int = Query(2, ge=0, le=10, description="Target YOE for match_score calculation (default: 2)"),
    include_stats: bool = Query(False, description="Include system resource stats in response"),
) -> JobsResponse:
    try:
        all_jobs: List[Job] = load_jobs()
        if not all_jobs:
            return JobsResponse(ok=True, count=0, jobs=[])

        cutoff = datetime.utcnow() - timedelta(days=days)
        filtered: List[Job] = []
        q_lower = q.lower() if q else None

        for job in all_jobs:
            # Date filter
            if job.date and job.date < cutoff:
                continue
            # Source filter
            if source and job.source != source:
                continue
            # Query filter
            if q_lower:
                text = f"{job.title} {job.company} {job.location} {job.description}".lower()
                if q_lower not in text:
                    continue
            # YOE filter
            if yoe_min is not None:
                if job.yoe_max is not None and job.yoe_max < yoe_min:
                    continue
                if job.yoe_min is not None and job.yoe_min > yoe_min:
                    continue
            if yoe_max is not None:
                if job.yoe_min is not None and job.yoe_min > yoe_max:
                    continue
                if job.yoe_max is not None and job.yoe_max > yoe_max:
                    continue
            # Exclude 5+ YOE by default (unless explicitly requested)
            if yoe_max is None and job.yoe_min is not None and job.yoe_min >= 5:
                continue
            if job.yoe_max is not None and job.yoe_max >= 5 and (yoe_max is None or yoe_max < 5):
                continue
            
            # Calculate/update match_score if not set
            if job.match_score is None:
                try:
                    job.match_score = calculate_match_score(
                        job.title, job.description, job.location,
                        job.yoe_min, job.yoe_max, target_yoe
                    )
                except Exception as e:
                    # If scoring fails, set default score
                    print(f"Warning: Match score calculation failed: {e}")
                    job.match_score = 50.0  # Default neutral score
            
            filtered.append(job)

        # Sort
        if sort == "relevance":
            filtered.sort(key=lambda j: (j.match_score or 0.0, j.date or datetime.min), reverse=True)
        elif sort == "source":
            filtered.sort(key=lambda j: (j.source, j.date or datetime.min), reverse=True)
        else:  # default: date
            filtered.sort(key=lambda j: (j.date or datetime.min), reverse=True)
        
        total = len(filtered)

        if page is not None and per_page is not None:
            start = (page - 1) * per_page
            limited = filtered[start : start + per_page]
            response = JobsResponse(
                ok=True, count=len(limited), jobs=limited,
                total=total, page=page, per_page=per_page,
            )
        else:
            limited = filtered[:limit]
            response = JobsResponse(ok=True, count=len(limited), jobs=limited)
        
        # Add system stats if requested
        if include_stats:
            try:
                import psutil
                memory = psutil.virtual_memory()
                cpu_percent = psutil.cpu_percent(interval=0.1)
                process = psutil.Process()
                process_memory_mb = process.memory_info().rss / (1024 * 1024)
                
                import os
                from pathlib import Path
                data_dir = os.environ.get("JOBS_SCRAPER_DATA_DIR", "data")
                disk_path = Path(data_dir) if Path(data_dir).exists() else Path("/")
                disk = psutil.disk_usage(str(disk_path))
                
                from .models import SystemStats
                response.system = SystemStats(
                    cpu_percent=round(cpu_percent, 2),
                    memory_percent=round(memory.percent, 2),
                    memory_used_mb=round(memory.used / (1024 * 1024), 2),
                    memory_total_mb=round(memory.total / (1024 * 1024), 2),
                    disk_percent=round(disk.percent, 2),
                    disk_used_gb=round(disk.used / (1024 * 1024 * 1024), 2),
                    disk_total_gb=round(disk.total / (1024 * 1024 * 1024), 2),
                    process_memory_mb=round(process_memory_mb, 2),
                )
            except Exception:
                pass  # Stats optional, don't fail if unavailable
        
        return response
    except Exception as e:
        # Return error as JSON instead of 500
        import traceback
        error_detail = str(e)
        print(f"Error in /jobs endpoint: {error_detail}")
        print(traceback.format_exc())
        return JobsResponse(
            ok=False,
            count=0,
            jobs=[],
            error=error_detail[:500],
        )


@app.get("/jobs/grouped-by-currency", response_model=GroupedByCurrencyResponse)
async def get_jobs_grouped_by_currency(
    q: Optional[str] = Query(None, description="Free text query"),
    days: int = Query(3, ge=1, le=30),
    source: Optional[str] = Query(None),
    yoe_min: Optional[int] = Query(None, ge=0),
    yoe_max: Optional[int] = Query(None, ge=0),
) -> GroupedByCurrencyResponse:
    """
    Get jobs grouped by currency (USD, INR, GBP, etc.).
    Jobs without currency go under "unknown". Useful for UI navigation.
    """
    try:
        all_jobs: List[Job] = load_jobs()
        if not all_jobs:
            return GroupedByCurrencyResponse(ok=True, currencies={})

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
            if yoe_min is not None:
                if job.yoe_max is not None and job.yoe_max < yoe_min:
                    continue
                if job.yoe_min is not None and job.yoe_min > yoe_min:
                    continue
            if yoe_max is not None:
                if job.yoe_min is not None and job.yoe_min > yoe_max:
                    continue
                if job.yoe_max is not None and job.yoe_max > yoe_max:
                    continue
            if yoe_max is None and job.yoe_min is not None and job.yoe_min >= 5:
                continue
            if job.yoe_max is not None and job.yoe_max >= 5 and (yoe_max is None or yoe_max < 5):
                continue
            filtered.append(job)

        currencies: dict = {}
        for job in filtered:
            curr = (job.currency or "unknown").strip().upper() or "unknown"
            if curr not in currencies:
                currencies[curr] = []
            currencies[curr].append(job)

        return GroupedByCurrencyResponse(ok=True, currencies=currencies)
    except Exception as e:
        return GroupedByCurrencyResponse(ok=False, currencies={}, error=str(e)[:500])


@app.get("/jobs/rss", response_class=Response)
async def get_jobs_rss(
    request: Request,
    q: Optional[str] = Query(None, description="Free text query, e.g. 'data analyst'"),
    days: int = Query(3, ge=1, le=30, description="Max age of jobs in days"),
    limit: int = Query(100, ge=1, le=400, description="Max items in RSS feed"),
    source: Optional[str] = Query(None, description="Filter by source id"),
) -> Response:
    """
    Lightweight RSS feed over the stored jobs.
    Intended for quick UI experiments and RSS-style consumption.
    """
    all_jobs: List[Job] = load_jobs()
    if not all_jobs:
        rss_empty = """<?xml version="1.0" encoding="UTF-8"?><rss version="2.0"><channel><title>Jobs RSS</title><link>{link}</link><description>No jobs available</description></channel></rss>""".format(
            link=html.escape(str(request.url))
        )
        return Response(content=rss_empty, media_type="application/rss+xml")

    cutoff = datetime.utcnow() - timedelta(days=days)
    q_lower = q.lower() if q else None
    filtered: List[Job] = []

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

    # Sort newest first and apply limit
    filtered.sort(key=lambda j: (j.date or datetime.min), reverse=True)
    jobs = filtered[:limit]

    base_link = str(request.base_url).rstrip("/")
    channel_link = f"{base_link}/jobs/rss"

    items_xml = []
    for job in jobs:
        title = html.escape(job.title or "Untitled job")
        link = html.escape(str(job.url))
        description_parts = [
            job.company or "",
            job.location or "",
        ]
        if job.description:
            description_parts.append(job.description[:400])
        description = html.escape(" | ".join(p for p in description_parts if p))
        pub_date = (
            job.date.strftime("%a, %d %b %Y %H:%M:%S GMT")
            if job.date
            else datetime.utcnow().strftime("%a, %d %b %Y %H:%M:%S GMT")
        )
        source_tag = html.escape(job.source or "")
        items_xml.append(
            f"<item><title>{title}</title><link>{link}</link>"
            f"<description>{description}</description>"
            f"<pubDate>{pub_date}</pubDate>"
            f"<category>{source_tag}</category>"
            f"</item>"
        )

    rss_xml = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<rss version="2.0"><channel>'
        f"<title>Jobs RSS</title>"
        f"<link>{html.escape(channel_link)}</link>"
        "<description>Jobs feed from job-search-api</description>"
        + "".join(items_xml)
        + "</channel></rss>"
    )

    return Response(content=rss_xml, media_type="application/rss+xml")


@app.post("/refresh", response_model=JobsResponse)
async def refresh_jobs(
    q: Optional[str] = Query("data analyst", description="Default search query"),
    days: int = Query(3, ge=1, le=30),
    headless: Optional[bool] = Query(None, description="Include headless scrapers (default: from ENABLE_HEADLESS env). Use headless=0 for quick RSS-only refresh."),
    include_stats: bool = Query(False, description="Include system resource stats in response"),
) -> JobsResponse:
    enable_headless = headless if headless is not None else True
    jobs = await scrape_all(days=days, query=q, enable_headless=enable_headless)
    save_jobs(jobs)
    
    response = JobsResponse(ok=True, count=len(jobs), jobs=jobs)
    
    # Add system stats if requested
    if include_stats:
        try:
            import psutil
            memory = psutil.virtual_memory()
            cpu_percent = psutil.cpu_percent(interval=0.1)
            process = psutil.Process()
            process_memory_mb = process.memory_info().rss / (1024 * 1024)
            
            import os
            from pathlib import Path
            data_dir = os.environ.get("JOBS_SCRAPER_DATA_DIR", "data")
            disk_path = Path(data_dir) if Path(data_dir).exists() else Path("/")
            disk = psutil.disk_usage(str(disk_path))
            
            from .models import SystemStats
            response.system = SystemStats(
                cpu_percent=round(cpu_percent, 2),
                memory_percent=round(memory.percent, 2),
                memory_used_mb=round(memory.used / (1024 * 1024), 2),
                memory_total_mb=round(memory.total / (1024 * 1024), 2),
                disk_percent=round(disk.percent, 2),
                disk_used_gb=round(disk.used / (1024 * 1024 * 1024), 2),
                disk_total_gb=round(disk.total / (1024 * 1024 * 1024), 2),
                process_memory_mb=round(process_memory_mb, 2),
            )
        except Exception:
            pass  # Stats optional
    
    return response


@app.get("/debug")
async def debug_scrapers() -> dict:
    """
    Debug endpoint: test all 14 RSS/HTTP scrapers. Fast; no headless.
    """
    import asyncio
    from .scraper import (
        scrape_weworkremotely,
        scrape_jobscollider,
        scrape_remoteok,
        scrape_remotive_api,
        scrape_remotive_rss,
        scrape_remotive_data_feed,
        scrape_remotive_ai_ml_feed,
        scrape_wellfound,
        scrape_indeed_rss,
        scrape_remote_co,
        scrape_jobspresso,
        scrape_himalayas,
        scrape_authentic_jobs,
        scrape_stackoverflow_jobs,
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
        "remotive_data": scrape_remotive_data_feed,
        "remotive_ai_ml": scrape_remotive_ai_ml_feed,
        "wellfound": scrape_wellfound,
        "indeed_rss": scrape_indeed_rss,
        "remote_co": scrape_remote_co,
        "jobspresso": scrape_jobspresso,
        "himalayas": scrape_himalayas,
        "authentic_jobs": scrape_authentic_jobs,
        "stackoverflow": scrape_stackoverflow_jobs,
    }
    for name, scraper_func in scrapers.items():
        try:
            # Add timeout per scraper (30 seconds)
            jobs = await asyncio.wait_for(
                scraper_func(days=test_days, query=test_query),
                timeout=30.0
            )
            results[name] = {"ok": True, "count": len(jobs), "error": None}
        except asyncio.TimeoutError:
            results[name] = {"ok": False, "count": 0, "error": "timeout (30s)"}
        except Exception as e:
            results[name] = {"ok": False, "count": 0, "error": str(e)[:200]}  # Limit error length
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
        scrape_hirist,
        scrape_foundit,
        scrape_shine,
        scrape_monster,
        scrape_glassdoor,
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
                    ("hirist", scrape_hirist),
                    ("foundit", scrape_foundit),
                    ("shine", scrape_shine),
                    ("monster", scrape_monster),
                    ("glassdoor", scrape_glassdoor),
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
