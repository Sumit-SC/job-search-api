from __future__ import annotations

import logging
import os
import sys
import time
from pathlib import Path
from datetime import datetime, timedelta, timezone
from typing import List, Optional

import html
import httpx
import feedparser
from dateutil import parser as dateparser
from fastapi import FastAPI, Header, Query, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from .models import Job, JobsResponse, GroupedByCurrencyResponse
from .scraper import scrape_all
from .storage import load_jobs, save_jobs
from .cache import (
    get_jobspy_cache,
    get_rssjobs_cache,
    get_cache_stats,
    jobspy_cache_key,
    rssjobs_cache_key,
)
from . import storage


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

# Serve local-ui static files on Railway (and locally) at /ui
_LOCAL_UI_DIR = Path(__file__).resolve().parent.parent / "local-ui"
if _LOCAL_UI_DIR.exists():
    app.mount("/ui", StaticFiles(directory=str(_LOCAL_UI_DIR), html=True), name="ui")


@app.get("/")
async def root() -> Response:
    """Redirect to the embedded UI so the Railway page loads the local-ui HTML."""
    from fastapi.responses import RedirectResponse
    return RedirectResponse(url="/ui/", status_code=302)


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


def _gather_system_info() -> dict:
    """Reusable system info for /api/monitor (same as /system without HTTP)."""
    try:
        import psutil
        data_dir = os.environ.get("JOBS_SCRAPER_DATA_DIR", "data")
        disk_path = Path(data_dir)
        if not disk_path.exists():
            disk_path = Path("/")
        memory = psutil.virtual_memory()
        disk = psutil.disk_usage(str(disk_path))
        process = psutil.Process()
        return {
            "ok": True,
            "cpu_percent": round(psutil.cpu_percent(interval=0.2), 2),
            "cpu_cores": psutil.cpu_count(),
            "memory_total_mb": round(memory.total / (1024 * 1024), 2),
            "memory_used_mb": round(memory.used / (1024 * 1024), 2),
            "memory_percent": round(memory.percent, 2),
            "disk_path": str(disk_path),
            "disk_free_gb": round(disk.free / (1024 ** 3), 2),
            "disk_percent": round(disk.percent, 2),
            "process_rss_mb": round(process.memory_info().rss / (1024 * 1024), 2),
            "railway_env": os.environ.get("RAILWAY_ENVIRONMENT"),
            "railway_service": os.environ.get("RAILWAY_SERVICE_NAME"),
        }
    except Exception as e:
        return {"ok": False, "error": str(e)}


@app.get("/api/monitor")
async def monitor_dashboard(
    request: Request,
    key: Optional[str] = Query(None),
    x_monitor_key: Optional[str] = Header(None, alias="X-Monitor-Key"),
) -> JSONResponse:
    """
    Protected monitor endpoint: system health, job DB, endpoint latencies, cache stats.
    Requires MONITOR_SECRET (Railway env var) via query ?key=SECRET or header X-Monitor-Key: SECRET.
    """
    secret = os.environ.get("MONITOR_SECRET", "").strip()
    if not secret:
        return JSONResponse(
            status_code=503,
            content={"ok": False, "error": "MONITOR_SECRET not configured"},
        )
    provided = (key or "").strip() or (x_monitor_key or "").strip()
    if provided != secret:
        return JSONResponse(status_code=401, content={"ok": False, "error": "Invalid key"})

    base_url = str(request.base_url).rstrip("/")
    checks: List[dict] = []
    ts = datetime.utcnow().isoformat() + "Z"

    # 1) Health self-ping
    try:
        t0 = time.perf_counter()
        async with httpx.AsyncClient(timeout=5.0) as client:
            r = await client.get(f"{base_url}/health")
        latency_ms = round((time.perf_counter() - t0) * 1000)
        checks.append({
            "name": "Health (self)",
            "status": "up" if r.status_code == 200 else "down",
            "latency_ms": latency_ms,
            "status_code": r.status_code,
            "detail": r.json() if r.status_code == 200 else None,
        })
    except Exception as e:
        checks.append({"name": "Health (self)", "status": "down", "error": str(e)[:200]})

    # 2) System resources
    try:
        sys_info = _gather_system_info()
        checks.append({
            "name": "System",
            "status": "up" if sys_info.get("ok") else "down",
            "detail": sys_info,
        })
    except Exception as e:
        checks.append({"name": "System", "status": "down", "error": str(e)[:200]})

    # 3) Job DB (file store)
    try:
        jobs = load_jobs()
        data_file = storage.DATA_FILE
        file_size = data_file.stat().st_size if data_file.exists() else 0
        mtime = datetime.fromtimestamp(data_file.stat().st_mtime, tz=timezone.utc).isoformat() if data_file.exists() else None
        checks.append({
            "name": "Job DB",
            "status": "up",
            "detail": {
                "job_count": len(jobs),
                "file_size_kb": round(file_size / 1024, 2),
                "file_path": str(data_file),
                "last_modified": mtime,
            },
        })
    except Exception as e:
        checks.append({"name": "Job DB", "status": "down", "error": str(e)[:200]})

    # 4) Endpoint latencies: /jobs, /system
    for path in ["/jobs?limit=1", "/system"]:
        try:
            t0 = time.perf_counter()
            async with httpx.AsyncClient(timeout=10.0) as client:
                r = await client.get(f"{base_url}{path}")
            latency_ms = round((time.perf_counter() - t0) * 1000)
            checks.append({
                "name": f"GET {path.split('?')[0]}",
                "status": "up" if r.status_code == 200 else "down",
                "latency_ms": latency_ms,
                "status_code": r.status_code,
            })
        except Exception as e:
            checks.append({"name": f"GET {path}", "status": "down", "error": str(e)[:200]})

    # 5) Cache stats
    try:
        cache_stats = get_cache_stats()
        checks.append({
            "name": "Cache (JobSpy / RSSJobs)",
            "status": "up",
            "detail": cache_stats,
        })
    except Exception as e:
        checks.append({"name": "Cache", "status": "down", "error": str(e)[:200]})

    # 6) Available API endpoints (for docs + test buttons)
    endpoints_list: List[dict] = []
    try:
        for route in request.app.routes:
            if not hasattr(route, "path") or not hasattr(route, "methods"):
                continue
            path = getattr(route, "path", "") or ""
            if path.startswith("/ui") or path in ("/openapi.json", "/docs", "/redoc"):
                continue
            methods = getattr(route, "methods", set()) or set()
            summary = getattr(route, "summary", None) or getattr(route, "name", "") or ""
            for method in sorted(methods):
                if method == "HEAD":
                    continue
                endpoints_list.append({
                    "method": method,
                    "path": path,
                    "summary": summary[:80] if summary else path,
                })
        endpoints_list.sort(key=lambda x: (x["path"], x["method"]))
    except Exception:
        pass

    return JSONResponse(content={
        "ok": True,
        "timestamp": ts,
        "checks": checks,
        "endpoints": endpoints_list,
    })


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
            # Date filter - normalize datetime before comparison
            job_date_normalized = normalize_datetime(job.date)
            if job_date_normalized and job_date_normalized < cutoff:
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

        # Sort - normalize datetimes before sorting
        if sort == "relevance":
            filtered.sort(key=lambda j: (j.match_score or 0.0, normalize_datetime(j.date) or datetime.min), reverse=True)
        elif sort == "source":
            filtered.sort(key=lambda j: (j.source, normalize_datetime(j.date) or datetime.min), reverse=True)
        else:  # default: date
            filtered.sort(key=lambda j: (normalize_datetime(j.date) or datetime.min), reverse=True)
        
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
            # Normalize datetime before comparison
            job_date_normalized = normalize_datetime(job.date)
            if job_date_normalized and job_date_normalized < cutoff:
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
        # Normalize datetime before comparison
        job_date_normalized = normalize_datetime(job.date)
        if job_date_normalized and job_date_normalized < cutoff:
            continue
        if source and job.source != source:
            continue
        if q_lower:
            text = f"{job.title} {job.company} {job.location} {job.description}".lower()
            if q_lower not in text:
                continue
        filtered.append(job)

    # Sort newest first and apply limit - normalize datetime before sorting
    filtered.sort(key=lambda j: (normalize_datetime(j.date) or datetime.min), reverse=True)
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
    mode: Optional[str] = Query(None, description="Source mode: 'rss', 'headless', or 'all' (default)."),
    include_stats: bool = Query(False, description="Include system resource stats in response"),
) -> JobsResponse:
    normalized_mode = (mode or "all").lower()
    if normalized_mode not in ("rss", "headless", "all"):
        normalized_mode = "all"

    enable_headless = headless if headless is not None else True
    jobs = await scrape_all(days=days, query=q, enable_headless=enable_headless, mode=normalized_mode)
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


def _jobs_response_headers(cache_hit: bool, max_age: int = 900) -> dict:
    """Cache-Control and X-Cache headers for job list responses."""
    return {
        "X-Cache": "HIT" if cache_hit else "MISS",
        "Cache-Control": f"private, max-age={max_age}",
    }


@app.get("/jobspy", response_model=JobsResponse)
async def jobspy_jobs(
    q: Optional[str] = Query(None, description="Search term for jobspy-backed boards"),
    location: Optional[str] = Query(None, description="Location string passed to jobspy (city, country, etc.)"),
    days: int = Query(3, ge=1, le=30, description="Max age of jobs in days (converted to hours_old for jobspy)"),
    limit: int = Query(100, ge=1, le=400, description="Max results per response"),
    sites: Optional[str] = Query(None, description="Comma-separated site names (e.g. indeed,linkedin,glassdoor,naukri)"),
    preset: Optional[str] = Query(None, description="Preset: popular, remote, or all"),
    country: Optional[str] = Query("usa", description="Country for Indeed/Glassdoor (usa, india, uk, etc.)"),
    is_remote: bool = Query(False, description="Filter for remote-only jobs"),
    skip_cache: bool = Query(False, description="If true, bypass server cache and re-scrape"),
) -> Response:
    """
    Fetch jobs from python-jobspy. Use sites= or preset= (popular, remote, all) to choose boards.
    Supported sites: indeed, linkedin, zip_recruiter, glassdoor, google, bayt, naukri, bdjobs.
    Responses are cached server-side for 15 minutes; use skip_cache=true to force a fresh scrape.
    """
    try:
        from .jobspy_integration import scrape_jobspy_sources
    except ImportError:
        return JSONResponse(
            status_code=200,
            content={"ok": False, "count": 0, "jobs": [], "error": "python-jobspy is not installed"},
            headers=_jobs_response_headers(False),
        )

    key = jobspy_cache_key(q, location, days, limit, sites, preset, country or "usa", is_remote)
    cache = get_jobspy_cache()
    if not skip_cache:
        cached = cache.get(key)
        if cached is not None:
            return JSONResponse(
                content=cached,
                headers=_jobs_response_headers(True),
            )

    site_list = [x.strip() for x in sites.split(",")] if sites and sites.strip() else None
    jobs = await scrape_jobspy_sources(
        days=days, query=q, location=location, results_wanted=limit,
        site_name=site_list, preset=preset,
        country_indeed=(country or "usa").strip().lower(),
        is_remote=is_remote,
    )
    response = JobsResponse(ok=True, count=len(jobs), jobs=jobs)
    payload = response.model_dump(mode="json")
    cache.set(key, payload)
    return JSONResponse(content=payload, headers=_jobs_response_headers(False))


@app.get("/rssjobs", response_model=JobsResponse)
async def rssjobs_proxy(
    keywords: str = Query(..., description="Job keywords/role (e.g., 'data analyst')"),
    location: str = Query("remote", description="Location (e.g., 'remote', 'pune', 'india')"),
    limit: int = Query(100, ge=1, le=400, description="Max results per response"),
    skip_cache: bool = Query(False, description="If true, bypass server cache"),
) -> Response:
    """
    Proxy endpoint for rssjobs.app feeds. Fetches RSS feed server-side (no CORS issues)
    and parses it into our Job model format. Cached 10 minutes; use skip_cache=true to refresh.
    """
    key = rssjobs_cache_key(keywords, location, limit)
    cache = get_rssjobs_cache()
    if not skip_cache:
        cached = cache.get(key)
        if cached is not None:
            return JSONResponse(content=cached, headers=_jobs_response_headers(True, max_age=600))

    try:
        feed_url = f"https://rssjobs.app/feeds?keywords={keywords}&location={location}"

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(feed_url)
            response.raise_for_status()
            xml_content = response.text

        if not xml_content:
            return JSONResponse(
                status_code=200,
                content={"ok": False, "count": 0, "jobs": [], "error": "Empty response from rssjobs.app"},
                headers=_jobs_response_headers(False),
            )

        # Parse RSS feed
        feed = feedparser.parse(xml_content)

        if feed.bozo and feed.bozo_exception:
            logger.warning(f"RSS parse error for rssjobs.app: {feed.bozo_exception}")
            return JSONResponse(
                status_code=200,
                content={"ok": False, "count": 0, "jobs": [], "error": f"RSS parse error: {feed.bozo_exception}"},
                headers=_jobs_response_headers(False),
            )

        jobs: List[Job] = []
        cutoff_date = datetime.utcnow() - timedelta(days=30)  # Max 30 days old

        for entry in feed.entries[:limit]:
            try:
                title = getattr(entry, "title", "") or ""
                link = getattr(entry, "link", "") or ""
                description = getattr(entry, "description", "") or getattr(entry, "summary", "") or ""
                published = getattr(entry, "published", "") or getattr(entry, "published_parsed", None)
                
                if not title or not link:
                    continue
                
                # Parse date using feedparser's parsed date (more reliable)
                dt: Optional[datetime] = None
                published_parsed = getattr(entry, "published_parsed", None)
                if published_parsed and isinstance(published_parsed, time.struct_time):
                    try:
                        # Convert struct_time to datetime
                        dt = datetime(*published_parsed[:6], tzinfo=timezone.utc)
                    except Exception:
                        dt = None
                elif published:
                    # Fallback: try parsing the string
                    try:
                        dt = dateparser.parse(published)
                        if dt and dt.tzinfo is None:
                            dt = dt.replace(tzinfo=timezone.utc)
                    except Exception:
                        dt = None
                
                # Filter by date if available
                if dt:
                    dt_normalized = normalize_datetime(dt)
                    if dt_normalized and dt_normalized < cutoff_date:
                        continue
                
                # Extract company/location from title or description if possible
                # rssjobs.app format: "Title: Company Name" or similar
                company = "Unknown"
                location_str = location.title()
                
                # Try to extract company from title (common format: "Job Title at Company")
                if " at " in title:
                    parts = title.split(" at ", 1)
                    if len(parts) == 2:
                        title = parts[0].strip()
                        company = parts[1].strip()
                
                job = Job(
                    id=f"rssjobs_{hash(link)}",
                    title=title,
                    company=company,
                    location=location_str,
                    url=link,
                    description=description[:2000] if description else "",  # Limit description length
                    source="rssjobs.app",
                    date=dt,
                    tags=["rssjobs"],
                )
                jobs.append(job)
            except Exception as e:
                logger.warning(f"Error processing rssjobs.app entry: {e}")
                continue

        response = JobsResponse(ok=True, count=len(jobs), jobs=jobs)
        payload = response.model_dump(mode="json")
        cache.set(key, payload)
        return JSONResponse(content=payload, headers=_jobs_response_headers(False, max_age=600))
    
    except httpx.TimeoutException:
        return JSONResponse(
            status_code=200,
            content={"ok": False, "count": 0, "jobs": [], "error": "Timeout fetching rssjobs.app feed"},
            headers=_jobs_response_headers(False),
        )
    except httpx.HTTPStatusError as e:
        return JSONResponse(
            status_code=200,
            content={"ok": False, "count": 0, "jobs": [], "error": f"HTTP error from rssjobs.app: {e.response.status_code}"},
            headers=_jobs_response_headers(False),
        )
    except Exception as e:
        logger.error(f"Error fetching rssjobs.app feed: {e}", exc_info=True)
        return JSONResponse(
            status_code=200,
            content={"ok": False, "count": 0, "jobs": [], "error": f"Error: {str(e)}"},
            headers=_jobs_response_headers(False),
        )


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
    Debug endpoint: test all 8 headless scrapers (LinkedIn, Indeed, Naukri, Hirist, Foundit, Shine, Monster, Glassdoor).
    Requires Playwright + ENABLE_HEADLESS=1. Can be slow (up to ~90s per scraper).
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
