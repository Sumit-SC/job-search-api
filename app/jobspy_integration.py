from __future__ import annotations

from datetime import datetime
from typing import List, Optional

import logging

from .models import Job

logger = logging.getLogger(__name__)

# python-jobspy (PyPI) supports only these sites; others cause KeyError in map_str_to_site
JOBSPY_SUPPORTED_SITES = [
    "indeed", "linkedin", "zip_recruiter", "glassdoor", "google",
    "bayt", "naukri", "bdjobs",
]
JOBSPY_PRESET_POPULAR = ["indeed", "linkedin", "zip_recruiter", "google", "glassdoor"]
JOBSPY_PRESET_REMOTE = ["indeed", "linkedin", "zip_recruiter", "google", "glassdoor"]  # same boards, use location=Remote
JOBSPY_ALL_BOARDS = list(JOBSPY_SUPPORTED_SITES)


def resolve_jobspy_sites(sites: Optional[List[str]] = None, preset: Optional[str] = None) -> List[str]:
    """Resolve site list from explicit sites or preset (popular, remote, all). Only returns supported sites."""
    supported = set(JOBSPY_SUPPORTED_SITES)
    if sites:
        resolved = [s.strip().lower() for s in sites if s and s.strip() and s.strip().lower() in supported]
        return resolved if resolved else list(JOBSPY_PRESET_POPULAR)
    if preset:
        p = preset.strip().lower()
        if p == "popular":
            return list(JOBSPY_PRESET_POPULAR)
        if p == "remote":
            return list(JOBSPY_PRESET_REMOTE)
        if p == "all":
            return list(JOBSPY_ALL_BOARDS)
    return list(JOBSPY_PRESET_POPULAR)


async def scrape_jobspy_sources(
    days: int = 3,
    query: Optional[str] = None,
    location: Optional[str] = None,
    results_wanted: int = 50,
    site_name: Optional[List[str]] = None,
    preset: Optional[str] = None,
    country_indeed: str = "usa",
    is_remote: bool = False,
) -> List[Job]:
    """
    Use python-jobspy to scrape job boards. site_name or preset selects boards.
    Scrapes each site separately and merges so one failing site does not block others.
    country_indeed is required for Indeed/Glassdoor (e.g. usa, india, uk).
    """
    try:
        from jobspy import scrape_jobs as jobspy_scrape_jobs  # type: ignore
    except Exception as e:  # pragma: no cover - dependency missing
        logger.error(f"python-jobspy not available: {e}")
        return []

    import asyncio

    sites = resolve_jobspy_sites(site_name, preset)
    hours_old = max(1, days * 24)
    wanted_per_site = max(10, min(results_wanted // max(1, len(sites)), 100))

    def _scrape_one_site(s: str):
        try:
            df = jobspy_scrape_jobs(
                site_name=[s],
                search_term=query or "",
                location=location or "",
                results_wanted=wanted_per_site,
                hours_old=hours_old,
                verbose=0,
                country_indeed=country_indeed,
                is_remote=is_remote,
            )
            return df.to_dict(orient="records") if df is not None and not df.empty else []
        except Exception as e:
            logger.warning(f"jobspy site {s} failed: {e}")
            return []

    def _run() -> List[Job]:
        seen_urls: set = set()
        all_records: List[dict] = []
        for s in sites:
            records = _scrape_one_site(s)
            for r in records:
                url = r.get("job_url") or r.get("JOB_URL") or ""
                if url and url not in seen_urls:
                    seen_urls.add(url)
                    all_records.append(r)

        jobs: List[Job] = []
        for r in all_records:
            try:
                title = r.get("title") or r.get("TITLE") or ""
                company = r.get("company") or r.get("COMPANY") or "Unknown"
                url = r.get("job_url") or r.get("JOB_URL") or ""
                if not url:
                    continue

                city = r.get("city") or r.get("CITY") or ""
                state = r.get("state") or r.get("STATE") or ""
                loc = ", ".join([p for p in [city, state] if p])
                if not loc:
                    loc = r.get("location") or r.get("LOCATION") or ""

                desc = r.get("description") or r.get("DESCRIPTION") or ""
                site = r.get("site") or r.get("SITE") or "jobspy"

                date_posted = r.get("date_posted") or r.get("DATE_POSTED")
                dt: Optional[datetime] = None
                if date_posted:
                    try:
                        if isinstance(date_posted, datetime):
                            dt = date_posted
                        else:
                            dt = datetime.fromisoformat(str(date_posted))
                    except Exception:
                        dt = None

                currency = r.get("currency") or r.get("CURRENCY")
                min_amount = r.get("min_amount") or r.get("MIN_AMOUNT")
                max_amount = r.get("max_amount") or r.get("MAX_AMOUNT")
                is_remote = r.get("is_remote") or r.get("IS_REMOTE")
                job_type = r.get("job_type") or r.get("JOB_TYPE")

                location_str = loc or ("Remote" if is_remote else "")

                salary_min = float(min_amount) if isinstance(min_amount, (int, float)) else None
                salary_max = float(max_amount) if isinstance(max_amount, (int, float)) else None

                job = Job(
                    id=f"jobspy_{site}_{hash(url)}",
                    title=title,
                    company=company,
                    location=location_str or "Unknown",
                    url=url,
                    description=desc or "",
                    source=f"jobspy_{str(site).lower()}",
                    date=dt,
                    tags=["jobspy"],
                    salary_min=salary_min,
                    salary_max=salary_max,
                    currency=currency,
                    job_type=job_type,
                )
                jobs.append(job)
            except Exception as e:
                logger.warning(f"Failed to adapt jobspy record {r}: {e}")
                continue

        logger.info(f"jobspy returned {len(jobs)} jobs from {len(sites)} site(s)")
        return jobs

    return await asyncio.to_thread(_run)

