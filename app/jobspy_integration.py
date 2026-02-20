from __future__ import annotations

from datetime import datetime
from typing import List, Optional

import logging

from .models import Job

logger = logging.getLogger(__name__)


async def scrape_jobspy_sources(
    days: int = 3,
    query: Optional[str] = None,
    location: Optional[str] = None,
    results_wanted: int = 50,
) -> List[Job]:
    """
    Use python-jobspy to scrape multiple job boards (LinkedIn, Indeed, Glassdoor, ZipRecruiter).

    This runs the synchronous jobspy scraper in a background thread and adapts
    the resulting DataFrame into our internal Job model.
    """
    try:
        from jobspy import scrape_jobs as jobspy_scrape_jobs  # type: ignore
    except Exception as e:  # pragma: no cover - dependency missing
        logger.error(f"python-jobspy not available: {e}")
        return []

    import asyncio

    def _run() -> List[Job]:
        try:
            hours_old = max(1, days * 24)
            # Clamp results for speed; JobSpy can be slow if this is very high
            wanted = max(10, min(results_wanted, 100))
            df = jobspy_scrape_jobs(
                site_name=["indeed", "linkedin", "glassdoor", "zip_recruiter"],
                search_term=query or "",
                location=location or "",
                results_wanted=wanted,
                hours_old=hours_old,
                verbose=0,
            )
        except Exception as e:
            logger.error(f"jobspy scrape_jobs failed: {e}", exc_info=True)
            return []

        try:
            records = df.to_dict(orient="records")
        except Exception as e:
            logger.error(f"jobspy DataFrame to_dict failed: {e}", exc_info=True)
            return []

        jobs: List[Job] = []
        for r in records:
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

        logger.info(f"jobspy returned {len(jobs)} jobs")
        return jobs

    return await asyncio.to_thread(_run)

