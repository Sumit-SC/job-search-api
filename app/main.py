from __future__ import annotations

import logging
import os
import sys
import time
import asyncio
from pathlib import Path
from datetime import datetime, timedelta, timezone
from typing import List, Optional
from urllib.parse import urlparse

try:
    from dotenv import load_dotenv  # type: ignore
    load_dotenv()
except Exception:
    # Optional dependency for local/dev; Railway can provide env vars directly.
    pass

import html
import httpx
import feedparser
from dateutil import parser as dateparser
from fastapi import FastAPI, Header, Query, Request, Response, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from .models import Job, JobsResponse, GroupedByCurrencyResponse, WebSearchResponse, WebSearchResult
from .scraper import scrape_all, get_proxy_stats
from .storage import load_jobs, save_jobs, load_saved_at

def stable_hash(text: str | int | float) -> int:
    import hashlib
    h = hashlib.md5(str(text).encode('utf-8')).hexdigest()
    return int(h[:8], 16)

hash = stable_hash
from .bot import notify_telegram
from .cache import (
    get_jobspy_cache,
    get_rssjobs_cache,
    get_cache_stats,
    jobspy_cache_key,
    rssjobs_cache_key,
)
from . import storage
from .agent import (
    AgentProfile,
    AgentRunResult,
    diff_jobs,
    filter_jobs,
    load_last_run_jobs,
    load_profile,
    save_last_run,
    save_profile,
    enrich_and_score,
)


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
from logging.handlers import RotatingFileHandler
os.makedirs("data", exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        RotatingFileHandler("data/app.log", maxBytes=5*1024*1024, backupCount=1, encoding="utf-8")
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


app = FastAPI(
    title="Jobs Scraper API",
    version="0.1.0",
    description="REST API for job listings. All documented endpoints return **JSON** (or RSS XML for `/jobs/rss` only). Use `/ui/` for the web UI.",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


async def schedule_scraping_loop() -> None:
    """Infinite loop to periodically scrape and notify new jobs."""
    try:
        val = os.environ.get("SCRAPE_INTERVAL_HOURS", "2.0").strip()
        interval_hours = float(val) if val else 2.0
    except Exception:
        interval_hours = 2.0
        
    logging.info(f"Starting background scraping loop. Interval: {interval_hours} hours.")
    
    # 2-minute delay on startup to allow container boot to stabilize
    await asyncio.sleep(120)
    
    while True:
        try:
            logging.info("Triggering scheduled background scrape...")
            existing_jobs = load_jobs()
            existing_urls = {j.url for j in existing_jobs if j.url}
            
            enable_headless = os.getenv("ENABLE_HEADLESS", "0") == "1"
            jobs = await scrape_all(days=3, query="data analyst", enable_headless=enable_headless, mode="all")
            save_jobs(jobs)
            
            new_jobs = [j for j in jobs if j.url and j.url not in existing_urls]
            if new_jobs:
                await notify_telegram(new_jobs)
                
            logging.info("Scheduled background scrape completed successfully.")
        except Exception as e:
            logging.error(f"Error in scheduled background scrape: {e}")
            
        await asyncio.sleep(interval_hours * 3600)


@app.on_event("startup")
async def startup_event() -> None:
    # Disable duplicate in-app scraping loop on boot to conserve CPU/RAM on Render
    # asyncio.create_task(schedule_scraping_loop())
    from .bot import keep_awake_loop
    asyncio.create_task(keep_awake_loop())


@app.get("/websearch", response_model=WebSearchResponse)
async def websearch(
    q: Optional[str] = Query(None, description="Search query, e.g. data analyst remote"),
    provider: str = Query("serpapi", description="serpapi | brave"),
    engine: str = Query("google", description="When provider=serpapi: google | bing | ..."),
    location: Optional[str] = Query(None, description="Optional search location hint (provider-specific)"),
    limit: int = Query(10, ge=1, le=50, description="Max results to return"),
) -> WebSearchResponse:
    """
    Search job postings via a search-engine API (better coverage than scraping individual boards).

    Notes:
    - This endpoint requires API keys (provider-specific):
      - SERPAPI_API_KEY for provider=serpapi
      - BRAVE_SEARCH_API_KEY for provider=brave
    - Returns *links* (not full job details).
    """
    from .websearch import WebSearchError, websearch_jobs

    query = (q or "").strip()
    if not query:
        return WebSearchResponse(ok=True, count=0, results=[])

    try:
        items = await websearch_jobs(q=query, provider=provider, engine=engine, num=limit, location=location)
        results = [
            WebSearchResult(title=i.title, url=i.url, snippet=i.snippet or "", source=i.source or "websearch")
            for i in items
        ]
        return WebSearchResponse(ok=True, count=len(results), results=results)
    except WebSearchError as e:
        return WebSearchResponse(ok=False, count=0, results=[], error=str(e))
    except Exception as e:
        return WebSearchResponse(ok=False, count=0, results=[], error=f"websearch failed: {e}")

# Serve local-ui static files on Railway (and locally) at /ui
_LOCAL_UI_DIR = Path(__file__).resolve().parent.parent / "local-ui"
if _LOCAL_UI_DIR.exists():
    app.mount("/ui", StaticFiles(directory=str(_LOCAL_UI_DIR), html=True), name="ui")


@app.get("/", include_in_schema=False)
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

    # 6) Proxy stats
    try:
        pstats = get_proxy_stats()
        checks.append({
            "name": "Proxy Pool",
            "status": "up" if pstats["enabled"] else "disabled",
            "detail": pstats,
        })
    except Exception as e:
        checks.append({"name": "Proxy Pool", "status": "error", "error": str(e)[:200]})

    # 7) Available API endpoints (for docs + test buttons)
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
    remote_only: bool = Query(False, description="If true, only include remote/WFH/distributed jobs (simple location text match)."),
    role_profile: Optional[str] = Query(
        None,
        description="Optional role profile filter. Use role_profile=data_analytics to focus results to analytics roles.",
    ),
    include_stats: bool = Query(False, description="Include system resource stats in response"),
) -> JobsResponse:
    try:
        all_jobs: List[Job] = load_jobs()
        saved_at_raw = load_saved_at()
        if not all_jobs:
            return JobsResponse(ok=True, count=0, jobs=[], generated_at=dateparser.parse(saved_at_raw) if saved_at_raw else None)
        if (page is None) != (per_page is None):
            return JobsResponse(
                ok=False,
                count=0,
                jobs=[],
                error="Use page and per_page together for pagination.",
                generated_at=dateparser.parse(saved_at_raw) if saved_at_raw else None,
            )

        def _is_remote_text(loc: str) -> bool:
            t = (loc or "").lower()
            return any(k in t for k in ["remote", "wfh", "work from home", "distributed", "anywhere", "home-based", "telecommute"])

        import re

        def _matches_query(job: Job, query: str | None) -> bool:
            if not query:
                return True
            title_text = f"{job.title}".lower()
            text = f"{job.title} {job.company} {job.location} {job.description}".lower()
            q_raw = query.lower().strip()
            if not q_raw:
                return True
            stop = {"and", "or", "the", "a", "an", "for", "to", "of", "in", "on", "with", "at"}
            tokens = [t for t in q_raw.replace("/", " ").replace(",", " ").split() if t and t not in stop]
            if not tokens:
                return True

            # Always allow exact phrase match.
            if q_raw in text:
                return True

            # Common analytics keywords are *allowed*, but no longer auto-include everything.
            title_role_kw = [
                "data analyst",
                "analyst",
                "analytics",
                "business intelligence",
                "product analyst",
                "business analyst",
                "analytics engineer",
                "decision scientist",
            ]

            def _title_role_hit(t: str) -> bool:
                # Avoid tiny-substring false positives like "bi" in "mobile".
                if re.search(r"\bbi\b", t, flags=re.IGNORECASE):
                    return True
                return any(k in t for k in title_role_kw)

            # Generic queries ("data", "analyst", "data analyst") should still be forgiving,
            # but must match either query tokens or analytics keywords.
            is_generic = len(tokens) <= 2
            if is_generic:
                # For generic queries, require either token hits anywhere OR role keywords in the TITLE.
                # This avoids matching random roles just because the description mentions "dashboards".
                return any(tok in title_text for tok in tokens) or _title_role_hit(title_text)

            # Specific queries: require at least 2 token hits (reduces random matches).
            hits = sum(1 for tok in tokens if tok in text)
            return hits >= 2 or _title_role_hit(title_text)

        def _matches_role_profile(job: Job, profile: str | None) -> bool:
            if not profile:
                return True
            p = str(profile).strip().lower()
            if p in {"none", "off", "all"}:
                return True
            if p != "data_analytics":
                return True
            title = (job.title or "").lower()
            # Allowlist (title-based) to keep relevance high.
            allow = [
                r"\bdata analyst\b",
                r"\bproduct analyst\b",
                r"\bbusiness analyst\b",
                r"\bbi analyst\b",
                r"\bbusiness intelligence\b",
                r"\banalytics engineer\b",
                r"\bdecision scientist\b",
                r"\bmarketing analyst\b",
                r"\bfinancial analyst\b",
                r"\boperations analyst\b",
                r"\banalyst\b",
            ]
            # Block obvious non-target analyst families.
            block = [
                r"\bquality analyst\b",
                r"\bbpo\b",
                r"\bcredit analyst\b",
                r"\brisk analyst\b",
                r"\bfraud\b",
                r"\bcompliance\b",
                r"\baudit\b",
                r"\bimmobilien\b",
                r"\baccounting\b",
                r"\bcontroller\b",
            ]
            if any(re.search(pat, title, flags=re.IGNORECASE) for pat in block):
                return False
            return any(re.search(pat, title, flags=re.IGNORECASE) for pat in allow)

        def _role_boost(job: Job, profile: str | None) -> float:
            if not profile:
                return 0.0
            p = str(profile).strip().lower()
            if p != "data_analytics":
                return 0.0
            title = (job.title or "").lower()
            if re.search(r"\bdata analyst\b", title, flags=re.IGNORECASE):
                return 20.0
            if re.search(r"\b(product|business) analyst\b", title, flags=re.IGNORECASE):
                return 15.0
            if re.search(r"\b(bi analyst|business intelligence)\b", title, flags=re.IGNORECASE):
                return 12.0
            if re.search(r"\banalytics engineer\b", title, flags=re.IGNORECASE):
                return 12.0
            if re.search(r"\banalyst\b", title, flags=re.IGNORECASE):
                return 6.0
            return 0.0

        cutoff = datetime.utcnow() - timedelta(days=days)
        filtered: List[Job] = []

        for job in all_jobs:
            # Date filter - normalize datetime before comparison
            job_date_normalized = normalize_datetime(job.date)
            if job_date_normalized and job_date_normalized < cutoff:
                continue
            # Source filter
            if source and job.source != source:
                continue
            # Remote-only filter (simple location text check)
            if remote_only and not _is_remote_text(job.location):
                continue
            # Query filter (token-based)
            if not _matches_query(job, q):
                continue
            # Role profile filter (optional)
            if not _matches_role_profile(job, role_profile):
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
            # Default experience preference (when not specified):
            # keep jobs with unknown yoe, but exclude jobs that clearly require 4+ years.
            if yoe_min is None and yoe_max is None:
                if job.yoe_min is not None and job.yoe_min >= 4:
                    continue
                if job.yoe_max is not None and job.yoe_max > 3:
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

            # Derived rank used for relevance ordering (safe, does not affect stored data).
            job.rank = float(job.match_score or 0.0) + _role_boost(job, role_profile)
            
            filtered.append(job)

        # Sort - normalize datetimes before sorting
        if sort == "relevance":
            filtered.sort(key=lambda j: (float(j.rank or 0.0), normalize_datetime(j.date) or datetime.min), reverse=True)
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
                generated_at=dateparser.parse(saved_at_raw) if saved_at_raw else None,
            )
        else:
            limited = filtered[:limit]
            response = JobsResponse(ok=True, count=len(limited), jobs=limited, generated_at=dateparser.parse(saved_at_raw) if saved_at_raw else None)
        
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


@app.get("/jobs/search", response_model=JobsResponse)
async def search_jobs(
    q: Optional[str] = Query(None, description="Free text query"),
    company: Optional[str] = Query(None, description="Filter by company name contains"),
    location: Optional[str] = Query(None, description="Filter by location contains"),
    days: int = Query(7, ge=1, le=30, description="Max age of jobs in days"),
    source_in: Optional[str] = Query(None, description="Comma-separated sources (e.g. remotive,remoteok,jobspy_linkedin)"),
    remote_only: bool = Query(False, description="If true, only include remote jobs"),
    role_profile: str = Query(
        "data_analytics",
        description="Role profile preset. Default data_analytics removes random roles and boosts analyst/analytics titles.",
    ),
    yoe_min: Optional[int] = Query(None, ge=0),
    yoe_max: Optional[int] = Query(None, ge=0),
    target_yoe: int = Query(2, ge=0, le=10),
    visa_required: Optional[bool] = Query(None, description="If true, only jobs mentioning visa sponsorship"),
    currency: Optional[str] = Query(None, description="Filter by salary currency code (USD, INR, GBP...)"),
    min_match_score: Optional[float] = Query(None, ge=0, le=100, description="Minimum match score"),
    job_type: Optional[str] = Query(None, description="Filter by job type (full_time, contract, etc.)"),
    sort: Optional[str] = Query("relevance", description="date | relevance | source"),
    page: int = Query(1, ge=1),
    per_page: int = Query(25, ge=1, le=100),
) -> JobsResponse:
    """
    Advanced search endpoint with richer filters and consistent pagination metadata.
    """
    base = await get_jobs(
        q=q,
        days=days,
        limit=400,
        source=None,
        page=None,
        per_page=None,
        sort=sort,
        yoe_min=yoe_min,
        yoe_max=yoe_max,
        target_yoe=target_yoe,
        remote_only=remote_only,
        role_profile=role_profile,
        include_stats=False,
    )
    if not base.ok:
        return base

    jobs = list(base.jobs or [])
    company_l = (company or "").strip().lower()
    location_l = (location or "").strip().lower()
    currency_u = (currency or "").strip().upper()
    job_type_l = (job_type or "").strip().lower()
    source_set = {
        s.strip().lower() for s in (source_in or "").split(",") if s and s.strip()
    }

    if company_l:
        jobs = [j for j in jobs if company_l in (j.company or "").lower()]
    if location_l:
        jobs = [j for j in jobs if location_l in (j.location or "").lower()]
    if source_set:
        jobs = [j for j in jobs if (j.source or "").lower() in source_set]
    if visa_required is True:
        jobs = [j for j in jobs if j.visa_sponsorship is True]
    if visa_required is False:
        jobs = [j for j in jobs if j.visa_sponsorship is not True]
    if currency_u:
        jobs = [j for j in jobs if (j.currency or "").upper() == currency_u]
    if min_match_score is not None:
        jobs = [j for j in jobs if float(j.match_score or 0.0) >= float(min_match_score)]
    if job_type_l:
        jobs = [j for j in jobs if (j.job_type or "").strip().lower() == job_type_l]

    total = len(jobs)
    start = (page - 1) * per_page
    paged = jobs[start : start + per_page]
    return JobsResponse(
        ok=True,
        count=len(paged),
        jobs=paged,
        total=total,
        page=page,
        per_page=per_page,
        generated_at=base.generated_at,
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
        job_dt: Optional[datetime] = None
        if isinstance(job.date, datetime):
            job_dt = normalize_datetime(job.date)
        elif job.date:
            try:
                parsed_dt = dateparser.parse(str(job.date))
                job_dt = normalize_datetime(parsed_dt) if parsed_dt else None
            except Exception:
                job_dt = None
        pub_date = (job_dt or datetime.utcnow()).strftime("%a, %d %b %Y %H:%M:%S GMT")
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


@app.post("/tg-webhook")
async def tg_webhook(request: Request, background_tasks: BackgroundTasks) -> dict:
    """Telegram Webhook entrypoint (delegates to the bot module)."""
    try:
        update = await request.json()
    except Exception:
        return {"ok": False, "error": "Invalid JSON"}
        
    from .bot import handle_tg_webhook
    # Delegate to background task so Telegram gets an instant 200 response (under 2ms)
    background_tasks.add_task(handle_tg_webhook, update, background_tasks)
    return {"ok": True}


async def run_refresh_task(q: str, days: int, enable_headless: bool, normalized_mode: str, source_list: list[str] | None):
    try:
        # Load existing jobs before scraping to compute the difference for Telegram notifications
        existing_jobs = load_jobs()
        existing_urls = {j.url for j in existing_jobs if j.url}
        
        jobs = await scrape_all(days=days, query=q, enable_headless=enable_headless, mode=normalized_mode, sources=source_list)
        save_jobs(jobs)
        
        # Identify new jobs
        new_jobs = [j for j in jobs if j.url and j.url not in existing_urls]
        if new_jobs:
            await notify_telegram(new_jobs)
    except Exception as e:
        logger.error(f"Error in background refresh task: {e}", exc_info=True)


@app.post("/refresh", response_model=JobsResponse)
async def refresh_jobs(
    background_tasks: BackgroundTasks,
    q: Optional[str] = Query("data analyst", description="Default search query"),
    days: int = Query(3, ge=1, le=30),
    headless: Optional[bool] = Query(None, description="Include headless scrapers (default: from ENABLE_HEADLESS env). Use headless=0 for quick RSS-only refresh."),
    mode: Optional[str] = Query(None, description="Source mode: 'rss', 'headless', or 'all' (default)."),
    fetch_profile: Optional[str] = Query(
        None,
        description="Preset refresh profile: basic (reliable RSS/API only) or advanced (all configured sources).",
    ),
    sources: Optional[str] = Query(None, description="Comma-separated source IDs to scrape (e.g. 'remoteok,remotive,hiring_cafe'). If empty, scrapes all."),
    include_stats: bool = Query(False, description="Include system resource stats in response"),
) -> JobsResponse:
    profile = (fetch_profile or "").strip().lower()
    normalized_mode = (mode or "all").lower()
    if normalized_mode not in ("rss", "headless", "all"):
        normalized_mode = "all"

    # Basic profile: use stable/maintained sources for fast, predictable refreshes.
    basic_sources = ["remoteok", "remotive", "hiring_cafe", "arbeitnow", "jobicy", "workingnomads"]
    source_list = [s.strip() for s in sources.split(",") if s.strip()] if sources else None
    if profile == "basic" and not source_list:
        source_list = basic_sources
        normalized_mode = "rss"
    elif profile == "advanced" and mode is None:
        normalized_mode = "all"

    enable_headless = headless if headless is not None else True
    
    # Launch scraper in background to avoid Render 50s timeout and GitHub Action connection drops
    background_tasks.add_task(
        run_refresh_task,
        q, days, enable_headless, normalized_mode, source_list
    )
    
    return JobsResponse(
        ok=True,
        count=0,
        jobs=[],
        generated_at=datetime.utcnow()
    )


@app.post("/jobs/batch", response_model=JobsResponse)
async def batch_add_jobs(
    jobs: List[Job],
    background_tasks: BackgroundTasks,
) -> JobsResponse:
    """
    Accept a list of jobs, persist them to Turso/SQLite, and notify Telegram if they are new.
    """
    if not jobs:
        return JobsResponse(ok=True, count=0, jobs=[])
        
    # Load existing to avoid duplicate Telegram alerts
    existing_jobs = load_jobs()
    existing_urls = {j.url for j in existing_jobs if j.url}
    
    # Save the incoming jobs (upserts conflict keys automatically)
    save_jobs(jobs)
    
    # Identify brand new listings for Telegram notifications
    new_jobs = [j for j in jobs if j.url and j.url not in existing_urls]
    if new_jobs and background_tasks:
        background_tasks.add_task(notify_telegram, new_jobs)
        
    return JobsResponse(
        ok=True,
        count=len(jobs),
        jobs=jobs,
        generated_at=datetime.utcnow()
    )


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
    Note: some sites (notably Naukri) may intermittently require reCAPTCHA and will then return 0 results.
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
    response = JobsResponse(ok=True, count=len(jobs), jobs=jobs, generated_at=datetime.utcnow())
    payload = response.model_dump(mode="json")
    cache.set(key, payload)
    return JSONResponse(content=payload, headers=_jobs_response_headers(False))


def sanitize_xml_content(xml_str: str) -> str:
    """Sanitize raw XML content to fix common validation and parsing issues before feedparser runs."""
    if not xml_str:
        return ""
    import re
    # Replace unescaped & with &amp;
    xml_str = re.sub(r'&(?!(?:amp|lt|gt|quot|apos|#\d+|#[xX][a-fA-F0-9]+);)', '&amp;', xml_str)
    # Remove invalid XML 1.0 control characters
    xml_str = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f]', '', xml_str)
    return xml_str


def _is_rssjobs_feed_url(url: str) -> bool:
    """Allow only rssjobs.app / www.rssjobs.app for feed_url (security)."""
    try:
        parsed = urlparse(url.strip())
        if parsed.scheme not in ("http", "https"):
            return False
        host = (parsed.netloc or "").lower()
        if host.startswith("www."):
            host = host[4:]
        return host == "rssjobs.app"
    except Exception:
        return False


@app.get("/rssjobs", response_model=JobsResponse)
async def rssjobs_proxy(
    keywords: Optional[str] = Query(None, description="Job keywords/role (e.g., 'data analyst'). Ignored if feed_url is set."),
    location: Optional[str] = Query("remote", description="Location (e.g., 'remote', 'pune'). Ignored if feed_url is set."),
    limit: int = Query(100, ge=1, le=400, description="Max results per response"),
    skip_cache: bool = Query(False, description="If true, bypass server cache"),
    feed_url: Optional[str] = Query(None, description="Your RSS feed URL from rssjobs.app (create feed there first, then paste URL here)."),
) -> Response:
    """
    Proxy endpoint for rssjobs.app feeds. Two modes:
    1) feed_url set: fetch and parse that RSS feed (create the feed at rssjobs.app first).
    2) keywords + location: build https://rssjobs.app/feeds?keywords=...&location=... (may fail for some combos).
    Cached 10 minutes; use skip_cache=true to refresh.
    """
    use_custom_feed = feed_url and _is_rssjobs_feed_url(feed_url)
    kw = (keywords or "").strip() or "data analyst"
    loc = (location or "").strip() or "remote"
    key = rssjobs_cache_key(kw, loc, limit, feed_url=feed_url if use_custom_feed else None)
    cache = get_rssjobs_cache()
    if not skip_cache:
        cached = cache.get(key)
        if cached is not None:
            return JSONResponse(content=cached, headers=_jobs_response_headers(True, max_age=600))

    try:
        if use_custom_feed:
            fetch_url = feed_url.strip()
        else:
            fetch_url = f"https://rssjobs.app/feeds?keywords={urllib.parse.quote(kw)}&location={urllib.parse.quote(loc)}"
            # Trigger feed generation via POST in background
            try:
                async with httpx.AsyncClient(timeout=10.0) as client:
                    await client.post(
                        "https://rssjobs.app/feeds",
                        data={"keywords": kw, "location": loc},
                        headers={"Content-Type": "application/x-www-form-urlencoded"}
                    )
            except Exception as e:
                logger.warning(f"rssjobs.app POST trigger failed: {e}")

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(fetch_url)
            response.raise_for_status()
            xml_content = response.text

        if not xml_content:
            return JSONResponse(
                status_code=200,
                content={"ok": False, "count": 0, "jobs": [], "error": "Empty response from rssjobs.app"},
                headers=_jobs_response_headers(False),
            )

        # Sanitize raw XML from external feed
        xml_content = sanitize_xml_content(xml_content)
        # Parse RSS feed
        feed = feedparser.parse(xml_content)

        if feed.bozo and feed.bozo_exception and not feed.entries:
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
                location_str = loc.title() if not use_custom_feed else "—"
                
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

        response = JobsResponse(ok=True, count=len(jobs), jobs=jobs, generated_at=datetime.utcnow())
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


@app.get("/agent/profile", response_model=AgentProfile)
async def get_agent_profile() -> AgentProfile:
    """Get the saved job-search agent profile (requirements)."""
    return load_profile()


@app.put("/agent/profile", response_model=AgentProfile)
async def put_agent_profile(profile: AgentProfile) -> AgentProfile:
    """Save/replace the job-search agent profile (requirements)."""
    save_profile(profile)
    return profile


@app.post("/agent/run", response_model=AgentRunResult)
async def run_agent(
    skip_cache: bool = Query(False, description="If true, bypass internal cache where possible"),
) -> AgentRunResult:
    """
    Run the job-search agent using the saved profile:
    - pulls jobs via existing scrapers (rss/headless/all)
    - enriches metadata (YOE/salary/visa)
    - scores + filters based on profile requirements
    - returns added/removed vs last run
    - stores snapshot for next diff
    """
    profile = load_profile()
    try:
        jobs = await scrape_all(
            days=profile.days,
            query=profile.query,
            enable_headless=profile.enable_headless,
            mode=profile.mode,
            sources=profile.sources,
        )

        scored: List[Job] = []
        for j in jobs:
            try:
                scored.append(enrich_and_score(j, profile))
            except Exception:
                if j.match_score is None:
                    j.match_score = 50.0
                if (j.rank or 0.0) <= 0.0 and j.match_score is not None:
                    j.rank = float(j.match_score)
                scored.append(j)

        filtered = filter_jobs(scored, profile)
        filtered.sort(key=lambda x: float(x.match_score or 0.0), reverse=True)

        prev = load_last_run_jobs()
        added, removed = diff_jobs(prev, filtered)

        save_last_run(profile, filtered)

        return AgentRunResult(
            ok=True,
            profile=profile,
            generated_at=datetime.now(timezone.utc),
            count=len(filtered),
            jobs=filtered,
            added=added,
            removed=removed,
        )
    except Exception as e:
        return AgentRunResult(
            ok=False,
            profile=profile,
            generated_at=datetime.now(timezone.utc),
            count=0,
            jobs=[],
            added=[],
            removed=[],
            error=str(e),
        )


@app.get("/proxy-stats")
async def proxy_stats_endpoint() -> dict:
    """Proxy pool usage stats — requests, successes, failures per proxy."""
    stats = get_proxy_stats()
    return {"ok": True, "proxy": stats}


@app.get("/debug")
async def debug_scrapers() -> dict:
    """
    Debug endpoint: test all RSS/HTTP/API scrapers. Fast; no headless.
    """
    import asyncio
    from .scraper import SCRAPER_REGISTRY
    results = {}
    test_query = "data analyst"
    test_days = 7
    scrapers = SCRAPER_REGISTRY
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


@app.get("/debug/telegram")
async def debug_telegram() -> dict:
    """Debug route to test Telegram Bot settings and check for errors."""
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
    chat_id = os.environ.get("TELEGRAM_CHANNEL_ID", "").strip()
    
    clean_token = token.strip('"').strip("'")
    clean_chat_id = chat_id.strip('"').strip("'")
    
    masked_chat_id = f"*******{clean_chat_id[-4:]}" if len(clean_chat_id) > 4 else "****"
    
    status = {
        "configured": {
            "token_present": bool(token),
            "chat_id_present": bool(chat_id),
            "token_length": len(token),
            "chat_id": masked_chat_id
        },
        "cleaned": {
            "token_length": len(clean_token),
            "chat_id": masked_chat_id
        }
    }
    
    if not clean_token or not clean_chat_id:
        return {"ok": False, "error": "Token or Chat ID missing", "status": status}
        
    url = f"https://api.telegram.org/bot{clean_token}/sendMessage"
    payload = {
        "chat_id": clean_chat_id,
        "text": "📢 <b>Debug Test</b>\nConnection from Render is working!",
        "parse_mode": "HTML"
    }
    
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            res = await client.post(url, json=payload)
            return {
                "ok": res.status_code == 200,
                "status_code": res.status_code,
                "status": status,
                "message": "Message sent successfully" if res.status_code == 200 else f"Failed to send: {res.text[:100]}"
            }
    except Exception as e:
        return {"ok": False, "error": "Internal transmission error", "status": status}


@app.get("/setup-webhook")
async def setup_webhook(request: Request) -> dict:
    """Automatically configure the Telegram webhook for this Render instance."""
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
    clean_token = token.strip('"').strip("'")
    if not clean_token:
        return {"ok": False, "error": "TELEGRAM_BOT_TOKEN not configured"}
        
    host = request.headers.get("host", "")
    if not host:
        return {"ok": False, "error": "Could not determine host header"}
        
    proto = "https" if "render.com" in host or "localhost" not in host else "http"
    webhook_url = f"{proto}://{host}/tg-webhook"
    
    tg_url = f"https://api.telegram.org/bot{clean_token}/setWebhook?url={webhook_url}"
    
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            res = await client.post(tg_url)
            return {
                "ok": res.status_code == 200,
                "status_code": res.status_code,
                "webhook_url": webhook_url,
                "telegram_response": res.json()
            }
    except Exception as e:
        return {"ok": False, "error": str(e)}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
