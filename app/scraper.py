from __future__ import annotations

import asyncio
from datetime import datetime, timedelta
from typing import List

import httpx
import feedparser
from dateutil import parser as dateparser

from .models import Job


USER_AGENT = "JobsScraper/1.0 (+https://github.com/Sumit-SC)"


async def fetch_text(client: httpx.AsyncClient, url: str, timeout: float = 15.0) -> str:
    try:
        resp = await client.get(url, headers={"User-Agent": USER_AGENT}, timeout=timeout)
        if resp.status_code != 200:
            return ""
        return resp.text
    except Exception:
        return ""


def _parse_date(value: str) -> datetime | None:
    if not value:
        return None
    try:
        return dateparser.parse(value)
    except Exception:
        return None


def _within_days(dt: datetime | None, max_days: int) -> bool:
    if dt is None:
        return True
    cutoff = datetime.utcnow() - timedelta(days=max_days)
    return dt >= cutoff


async def scrape_weworkremotely(days: int = 3, query: str | None = None) -> List[Job]:
    """
    Scrape WeWorkRemotely RSS feed.
    This is HTTP-only (no headless) but gives us solid remote analyst/BI roles.
    """
    url = "https://weworkremotely.com/remote-jobs.rss"
    async with httpx.AsyncClient() as client:
        xml = await fetch_text(client, url)
    if not xml:
        return []

    feed = feedparser.parse(xml)
    out: List[Job] = []
    for entry in feed.entries:
        title = getattr(entry, "title", "") or ""
        link = getattr(entry, "link", "") or ""
        summary = getattr(entry, "summary", "") or ""
        published = getattr(entry, "published", "") or ""
        dt = _parse_date(published)
        if not _within_days(dt, days):
            continue
        text = f"{title} {summary}".lower()
        if query and query.lower() not in text:
            continue
        if not link:
            continue
        job = Job(
            id=f"weworkremotely_{hash(link)}",
            title=title,
            company="Unknown",
            location="Remote",
            url=link,
            description=summary,
            source="weworkremotely",
            date=dt,
            tags=["rss"],
        )
        out.append(job)
    return out


async def scrape_jobscollider(days: int = 3, query: str | None = None) -> List[Job]:
    """
    Scrape Jobscollider / RemoteFirstJobs RSS feed.
    """
    url = "https://jobscollider.com/remote-jobs.rss"
    async with httpx.AsyncClient() as client:
        xml = await fetch_text(client, url)
    if not xml:
        return []
    feed = feedparser.parse(xml)
    out: List[Job] = []
    for entry in feed.entries:
        title = getattr(entry, "title", "") or ""
        link = getattr(entry, "link", "") or ""
        summary = getattr(entry, "summary", "") or ""
        published = getattr(entry, "published", "") or ""
        dt = _parse_date(published)
        if not _within_days(dt, days):
            continue
        text = f"{title} {summary}".lower()
        if query and query.lower() not in text:
            continue
        if not link:
            continue
        job = Job(
            id=f"jobscollider_{hash(link)}",
            title=title,
            company="Unknown",
            location="Remote",
            url=link,
            description=summary,
            source="jobscollider",
            date=dt,
            tags=["rss"],
        )
        out.append(job)
    return out


async def scrape_remoteok(days: int = 3, query: str | None = None) -> List[Job]:
    """
    Scrape RemoteOK RSS feed.
    """
    url = "https://remoteok.com/remote-jobs.rss"
    async with httpx.AsyncClient() as client:
        xml = await fetch_text(client, url)
    if not xml:
        return []
    feed = feedparser.parse(xml)
    out: List[Job] = []
    for entry in feed.entries:
        title = getattr(entry, "title", "") or ""
        link = getattr(entry, "link", "") or ""
        summary = getattr(entry, "summary", "") or ""
        published = getattr(entry, "published", "") or ""
        dt = _parse_date(published)
        if not _within_days(dt, days):
            continue
        text = f"{title} {summary}".lower()
        if query and query.lower() not in text:
            continue
        if not link:
            continue
        job = Job(
            id=f"remoteok_{hash(link)}",
            title=title,
            company="Unknown",
            location="Remote",
            url=link,
            description=summary,
            source="remoteok",
            date=dt,
            tags=["rss"],
        )
        out.append(job)
    return out


async def scrape_all(days: int = 3, query: str | None = None) -> List[Job]:
    """
    Aggregate all HTTP-based scrapers in parallel.
    Headless scrapers (Playwright) can be added here later.
    """
    tasks = [
        scrape_weworkremotely(days=days, query=query),
        scrape_jobscollider(days=days, query=query),
        scrape_remoteok(days=days, query=query),
    ]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    jobs: List[Job] = []
    seen = set()
    for res in results:
        if isinstance(res, Exception):
            continue
        for job in res:
            if job.url in seen:
                continue
            seen.add(job.url)
            jobs.append(job)
    return jobs
