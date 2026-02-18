from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from typing import List, Optional

import httpx
import feedparser
from dateutil import parser as dateparser

try:
    from playwright.async_api import async_playwright, Browser, Page
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False

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
    # Normalize both datetimes to UTC-naive for comparison
    if dt.tzinfo is not None:
        # Convert timezone-aware to UTC, then remove timezone info
        dt = dt.astimezone(timezone.utc).replace(tzinfo=None)
    cutoff = datetime.utcnow() - timedelta(days=max_days)
    return dt >= cutoff


async def scrape_weworkremotely(days: int = 3, query: str | None = None) -> List[Job]:
    """
    Scrape WeWorkRemotely RSS feed.
    This is HTTP-only (no headless) but gives us solid remote analyst/BI roles.
    """
    url = "https://weworkremotely.com/remote-jobs.rss"
    try:
        async with httpx.AsyncClient() as client:
            xml = await fetch_text(client, url)
        if not xml:
            return []

        feed = feedparser.parse(xml)
        out: List[Job] = []
        print(f"weworkremotely: Found {len(feed.entries)} RSS entries")
        for entry in feed.entries:
            title = getattr(entry, "title", "") or ""
            link = getattr(entry, "link", "") or ""
            summary = getattr(entry, "summary", "") or ""
            published = getattr(entry, "published", "") or ""
            dt = _parse_date(published)
            # Temporarily disable date filtering to see all jobs
            # if not _within_days(dt, days):
            #     continue
            # Temporarily disable query filtering to see all jobs
            # text = f"{title} {summary}".lower()
            # if query:
            #     query_lower = query.lower()
            #     if query_lower not in text and not any(kw in text for kw in ["data", "analyst", "analytics", "bi", "business intelligence"]):
            #         continue
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
    except Exception as e:
        print(f"Error scraping weworkremotely: {e}")
        return []


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
        # More lenient query filtering - check if query keywords appear anywhere
        if query:
            query_lower = query.lower()
            query_words = query_lower.split()
            text = f"{title} {summary}".lower()
            # Match if any query word appears, or if it's a data-related job
            if not any(word in text for word in query_words) and not any(kw in text for kw in ["data", "analyst", "analytics", "bi", "business intelligence"]):
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
        # More lenient query filtering - check if query keywords appear anywhere
        if query:
            query_lower = query.lower()
            query_words = query_lower.split()
            text = f"{title} {summary}".lower()
            # Match if any query word appears, or if it's a data-related job
            if not any(word in text for word in query_words) and not any(kw in text for kw in ["data", "analyst", "analytics", "bi", "business intelligence"]):
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


async def scrape_remotive_api(days: int = 3, query: str | None = None) -> List[Job]:
    """
    Scrape Remotive via their public API.
    """
    url = f"https://remotive.com/api/remote-jobs?search={query or 'data analyst'}"
    async with httpx.AsyncClient() as client:
        data = await client.get(url, headers={"User-Agent": USER_AGENT}, timeout=15.0)
        if data.status_code != 200:
            return []
        try:
            json_data = data.json()
        except Exception:
            return []
    
    jobs_list = json_data.get("jobs") or json_data.get("remote-jobs") or json_data.get("results") or []
    if not isinstance(jobs_list, list):
        return []
    
    out: List[Job] = []
    for item in jobs_list:
        if not item.get("title") or not item.get("url"):
            continue
        pub_date = item.get("publication_date") or item.get("created_at") or ""
        dt = _parse_date(pub_date)
        if not _within_days(dt, days):
            continue
        text = f"{item.get('title', '')} {item.get('description_plain', '') or item.get('description', '')}".lower()
        if query and query.lower() not in text:
            continue
        
        job = Job(
            id=f"remotive_{item.get('id', hash(item.get('url', '')))}",
            title=item.get("title", ""),
            company=item.get("company_name", "Unknown"),
            location=item.get("candidate_required_location") or item.get("location", "Remote"),
            url=item.get("url", ""),
            description=item.get("description_plain") or item.get("description", ""),
            source="remotive",
            date=dt,
            tags=["api"] + (item.get("tags", []) if isinstance(item.get("tags"), list) else []),
        )
        out.append(job)
    return out


async def scrape_remotive_rss(days: int = 3, query: str | None = None) -> List[Job]:
    """
    Scrape Remotive RSS feed.
    """
    urls = [
        "https://remotive.com/feed",
        "https://remotive.com/remote-jobs/feed/data",
        "https://remotive.com/remote-jobs/feed/ai-ml",
    ]
    out: List[Job] = []
    async with httpx.AsyncClient() as client:
        for url in urls:
            xml = await fetch_text(client, url)
            if not xml:
                continue
            feed = feedparser.parse(xml)
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
                    id=f"remotive_rss_{hash(link)}",
                    title=title,
                    company="Unknown",
                    location="Remote",
                    url=link,
                    description=summary,
                    source="remotive",
                    date=dt,
                    tags=["rss"],
                )
                out.append(job)
    return out


async def scrape_wellfound(days: int = 3, query: str | None = None) -> List[Job]:
    """
    Scrape Wellfound (formerly AngelList) RSS feeds.
    """
    urls = [
        "https://wellfound.com/jobs.rss?keywords=data-science&remote=true",
        "https://wellfound.com/jobs.rss?keywords=data-analyst&remote=true",
        "https://wellfound.com/jobs.rss?keywords=business-intelligence&remote=true",
    ]
    out: List[Job] = []
    async with httpx.AsyncClient() as client:
        for url in urls:
            xml = await fetch_text(client, url)
            if not xml:
                continue
            feed = feedparser.parse(xml)
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
                    id=f"wellfound_{hash(link)}",
                    title=title,
                    company="Unknown",
                    location="Remote",
                    url=link,
                    description=summary,
                    source="wellfound",
                    date=dt,
                    tags=["rss"],
                )
                out.append(job)
    return out


async def scrape_indeed_rss(days: int = 3, query: str | None = None) -> List[Job]:
    """
    Scrape Indeed RSS feed.
    """
    search_query = query or "data analyst"
    urls = [
        f"https://rss.indeed.com/rss?q={search_query.replace(' ', '+')}&l=remote&radius=0",
        f"https://rss.indeed.com/rss?q={search_query.replace(' ', '+')}+data+scientist&l=remote&radius=0",
    ]
    out: List[Job] = []
    async with httpx.AsyncClient() as client:
        for url in urls:
            xml = await fetch_text(client, url)
            if not xml:
                continue
            feed = feedparser.parse(xml)
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
                    id=f"indeed_rss_{hash(link)}",
                    title=title,
                    company="Unknown",
                    location="Remote",
                    url=link,
                    description=summary,
                    source="indeed",
                    date=dt,
                    tags=["rss"],
                )
                out.append(job)
    return out


async def scrape_remote_co(days: int = 3, query: str | None = None) -> List[Job]:
    """
    Scrape Remote.co RSS feed.
    """
    url = "https://remote.co/remote-jobs/feed/"
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
        # More lenient query filtering - check if query keywords appear anywhere
        if query:
            query_lower = query.lower()
            query_words = query_lower.split()
            text = f"{title} {summary}".lower()
            # Match if any query word appears, or if it's a data-related job
            if not any(word in text for word in query_words) and not any(kw in text for kw in ["data", "analyst", "analytics", "bi", "business intelligence"]):
                continue
        if not link:
            continue
        job = Job(
            id=f"remote_co_{hash(link)}",
            title=title,
            company="Unknown",
            location="Remote",
            url=link,
            description=summary,
            source="remote.co",
            date=dt,
            tags=["rss"],
        )
        out.append(job)
    return out


async def scrape_jobspresso(days: int = 3, query: str | None = None) -> List[Job]:
    """
    Scrape Jobspresso RSS feed.
    """
    url = "https://jobspresso.co/remote-jobs/feed/"
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
        # More lenient query filtering - check if query keywords appear anywhere
        if query:
            query_lower = query.lower()
            query_words = query_lower.split()
            text = f"{title} {summary}".lower()
            # Match if any query word appears, or if it's a data-related job
            if not any(word in text for word in query_words) and not any(kw in text for kw in ["data", "analyst", "analytics", "bi", "business intelligence"]):
                continue
        if not link:
            continue
        job = Job(
            id=f"jobspresso_{hash(link)}",
            title=title,
            company="Unknown",
            location="Remote",
            url=link,
            description=summary,
            source="jobspresso",
            date=dt,
            tags=["rss"],
        )
        out.append(job)
    return out


async def scrape_himalayas(days: int = 3, query: str | None = None) -> List[Job]:
    """
    Scrape Himalayas RSS feed.
    """
    url = "https://himalayas.app/jobs/feed"
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
        # More lenient query filtering - check if query keywords appear anywhere
        if query:
            query_lower = query.lower()
            query_words = query_lower.split()
            text = f"{title} {summary}".lower()
            # Match if any query word appears, or if it's a data-related job
            if not any(word in text for word in query_words) and not any(kw in text for kw in ["data", "analyst", "analytics", "bi", "business intelligence"]):
                continue
        if not link:
            continue
        job = Job(
            id=f"himalayas_{hash(link)}",
            title=title,
            company="Unknown",
            location="Remote",
            url=link,
            description=summary,
            source="himalayas",
            date=dt,
            tags=["rss"],
        )
        out.append(job)
    return out


async def scrape_authentic_jobs(days: int = 3, query: str | None = None) -> List[Job]:
    """
    Scrape Authentic Jobs RSS feed.
    """
    url = "https://authenticjobs.com/rss/"
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
        # More lenient query filtering - check if query keywords appear anywhere
        if query:
            query_lower = query.lower()
            query_words = query_lower.split()
            text = f"{title} {summary}".lower()
            # Match if any query word appears, or if it's a data-related job
            if not any(word in text for word in query_words) and not any(kw in text for kw in ["data", "analyst", "analytics", "bi", "business intelligence"]):
                continue
        if not link:
            continue
        job = Job(
            id=f"authentic_jobs_{hash(link)}",
            title=title,
            company="Unknown",
            location="Remote",
            url=link,
            description=summary,
            source="authentic_jobs",
            date=dt,
            tags=["rss"],
        )
        out.append(job)
    return out


# ============================================================================
# Playwright-based headless scrapers (for portals without RSS/API)
# ============================================================================

async def scrape_linkedin(days: int = 3, query: str | None = None, browser: Optional[Browser] = None) -> List[Job]:
    """
    Scrape LinkedIn Jobs using Playwright.
    Note: LinkedIn may block bots, so this may not always work.
    """
    if not PLAYWRIGHT_AVAILABLE:
        return []
    
    search_query = query or "data analyst"
    url = f"https://www.linkedin.com/jobs/search?keywords={search_query.replace(' ', '%20')}&location=remote&f_TPR=r259200&f_E=2,3&f_TP=1"
    
    try:
        if browser is None:
            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=True)
                page = await browser.new_page()
                await page.goto(url, wait_until="domcontentloaded", timeout=30000)
                await page.wait_for_selector(".jobs-search__results-list, [data-test-id='job-card']", timeout=15000)
                
                jobs_data = await page.evaluate("""
                    () => {
                        const jobs = [];
                        const cards = document.querySelectorAll('li[class*="job"], [data-test-id="job-card"]');
                        for (const card of cards) {
                            const link = card.querySelector('a[href*="/jobs/view/"]');
                            if (!link) continue;
                            const title = (link.textContent || '').trim();
                            if (!title) continue;
                            const href = link.getAttribute('href') || '';
                            const fullUrl = href.startsWith('/') ? 'https://www.linkedin.com' + href : href;
                            const companyEl = card.querySelector('.job-search-card__subtitle, [class*="company"]');
                            const locationEl = card.querySelector('.job-search-card__location, [class*="location"]');
                            const timeEl = card.querySelector('.job-search-card__listdate, time');
                            jobs.push({
                                title,
                                company: companyEl ? companyEl.textContent.trim() : 'Unknown',
                                location: locationEl ? locationEl.textContent.trim() : 'Remote',
                                url: fullUrl,
                                date: timeEl ? (timeEl.getAttribute('datetime') || timeEl.textContent.trim()) : '',
                            });
                            if (jobs.length >= 30) break;
                        }
                        return jobs;
                    }
                """)
                await browser.close()
        else:
            page = await browser.new_page()
            await page.goto(url, wait_until="domcontentloaded", timeout=30000)
            await page.wait_for_selector(".jobs-search__results-list, [data-test-id='job-card']", timeout=15000)
            jobs_data = await page.evaluate("""
                () => {
                    const jobs = [];
                    const cards = document.querySelectorAll('li[class*="job"], [data-test-id="job-card"]');
                    for (const card of cards) {
                        const link = card.querySelector('a[href*="/jobs/view/"]');
                        if (!link) continue;
                        const title = (link.textContent || '').trim();
                        if (!title) continue;
                        const href = link.getAttribute('href') || '';
                        const fullUrl = href.startsWith('/') ? 'https://www.linkedin.com' + href : href;
                        const companyEl = card.querySelector('.job-search-card__subtitle, [class*="company"]');
                        const locationEl = card.querySelector('.job-search-card__location, [class*="location"]');
                        const timeEl = card.querySelector('.job-search-card__listdate, time');
                        jobs.push({
                            title,
                            company: companyEl ? companyEl.textContent.trim() : 'Unknown',
                            location: locationEl ? locationEl.textContent.trim() : 'Remote',
                            url: fullUrl,
                            date: timeEl ? (timeEl.getAttribute('datetime') || timeEl.textContent.trim()) : '',
                        });
                        if (jobs.length >= 30) break;
                    }
                    return jobs;
                }
            """)
            await page.close()
        
        out: List[Job] = []
        for item in jobs_data:
            dt = _parse_date(item.get("date", ""))
            if not _within_days(dt, days):
                continue
            text = f"{item.get('title', '')} {item.get('company', '')}".lower()
            if query and query.lower() not in text:
                continue
            job = Job(
                id=f"linkedin_{hash(item.get('url', ''))}",
                title=item.get("title", ""),
                company=item.get("company", "Unknown"),
                location=item.get("location", "Remote"),
                url=item.get("url", ""),
                description="",
                source="linkedin",
                date=dt,
                tags=["headless"],
            )
            out.append(job)
        return out
    except Exception:
        return []


async def scrape_indeed_headless(days: int = 3, query: str | None = None, browser: Optional[Browser] = None) -> List[Job]:
    """
    Scrape Indeed Jobs using Playwright (headless browser).
    """
    if not PLAYWRIGHT_AVAILABLE:
        return []
    
    search_query = query or "data analyst"
    url = f"https://www.indeed.com/jobs?q={search_query.replace(' ', '+')}&l=remote&radius=0&fromage=3"
    
    try:
        if browser is None:
            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=True)
                page = await browser.new_page()
                await page.goto(url, wait_until="domcontentloaded", timeout=30000)
                await page.wait_for_selector(".job_seen_beacon, .jobCard", timeout=15000)
                
                jobs_data = await page.evaluate("""
                    () => {
                        const jobs = [];
                        const cards = document.querySelectorAll('.job_seen_beacon, .jobCard');
                        for (const card of cards) {
                            const titleEl = card.querySelector('h2.jobTitle a, a[data-jk]');
                            if (!titleEl) continue;
                            const title = (titleEl.textContent || '').trim();
                            const href = titleEl.getAttribute('href') || '';
                            const fullUrl = href.startsWith('/') ? 'https://www.indeed.com' + href : href;
                            const companyEl = card.querySelector('.companyName, [data-testid="company-name"]');
                            const locationEl = card.querySelector('.companyLocation, [data-testid="text-location"]');
                            const dateEl = card.querySelector('.date, [data-testid="myJobsStateDate"]');
                            jobs.push({
                                title,
                                company: companyEl ? companyEl.textContent.trim() : 'Unknown',
                                location: locationEl ? locationEl.textContent.trim() : 'Remote',
                                url: fullUrl,
                                date: dateEl ? dateEl.textContent.trim() : '',
                            });
                            if (jobs.length >= 30) break;
                        }
                        return jobs;
                    }
                """)
                await browser.close()
        else:
            page = await browser.new_page()
            await page.goto(url, wait_until="domcontentloaded", timeout=30000)
            await page.wait_for_selector(".job_seen_beacon, .jobCard", timeout=15000)
            jobs_data = await page.evaluate("""
                () => {
                    const jobs = [];
                    const cards = document.querySelectorAll('.job_seen_beacon, .jobCard');
                    for (const card of cards) {
                        const titleEl = card.querySelector('h2.jobTitle a, a[data-jk]');
                        if (!titleEl) continue;
                        const title = (titleEl.textContent || '').trim();
                        const href = titleEl.getAttribute('href') || '';
                        const fullUrl = href.startsWith('/') ? 'https://www.indeed.com' + href : href;
                        const companyEl = card.querySelector('.companyName, [data-testid="company-name"]');
                        const locationEl = card.querySelector('.companyLocation, [data-testid="text-location"]');
                        const dateEl = card.querySelector('.date, [data-testid="myJobsStateDate"]');
                        jobs.push({
                            title,
                            company: companyEl ? companyEl.textContent.trim() : 'Unknown',
                            location: locationEl ? locationEl.textContent.trim() : 'Remote',
                            url: fullUrl,
                            date: dateEl ? dateEl.textContent.trim() : '',
                        });
                        if (jobs.length >= 30) break;
                    }
                    return jobs;
                }
            """)
            await page.close()
        
        out: List[Job] = []
        for item in jobs_data:
            dt = _parse_date(item.get("date", ""))
            if not _within_days(dt, days):
                continue
            text = f"{item.get('title', '')} {item.get('company', '')}".lower()
            if query and query.lower() not in text:
                continue
            job = Job(
                id=f"indeed_headless_{hash(item.get('url', ''))}",
                title=item.get("title", ""),
                company=item.get("company", "Unknown"),
                location=item.get("location", "Remote"),
                url=item.get("url", ""),
                description="",
                source="indeed",
                date=dt,
                tags=["headless"],
            )
            out.append(job)
        return out
    except Exception:
        return []


async def scrape_naukri(days: int = 3, query: str | None = None, browser: Optional[Browser] = None) -> List[Job]:
    """
    Scrape Naukri.com (India) using Playwright.
    """
    if not PLAYWRIGHT_AVAILABLE:
        return []
    
    search_query = query or "data analyst"
    url = f"https://www.naukri.com/data-analyst-jobs?k={search_query.replace(' ', '%20')}&experience=2,3"
    
    try:
        if browser is None:
            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=True)
                page = await browser.new_page()
                await page.goto(url, wait_until="domcontentloaded", timeout=30000)
                await page.wait_for_selector(".jobTuple, .jobCard", timeout=15000)
                
                jobs_data = await page.evaluate("""
                    () => {
                        const jobs = [];
                        const cards = document.querySelectorAll('.jobTuple, .jobCard');
                        for (const card of cards) {
                            const titleEl = card.querySelector('a.title, .jobTitle a');
                            if (!titleEl) continue;
                            const title = (titleEl.textContent || '').trim();
                            const href = titleEl.getAttribute('href') || '';
                            const fullUrl = href.startsWith('/') ? 'https://www.naukri.com' + href : href;
                            const companyEl = card.querySelector('.companyName, .comp-name');
                            const locationEl = card.querySelector('.locWdth, .location');
                            const dateEl = card.querySelector('.date, .posted');
                            jobs.push({
                                title,
                                company: companyEl ? companyEl.textContent.trim() : 'Unknown',
                                location: locationEl ? locationEl.textContent.trim() : 'India',
                                url: fullUrl,
                                date: dateEl ? dateEl.textContent.trim() : '',
                            });
                            if (jobs.length >= 30) break;
                        }
                        return jobs;
                    }
                """)
                await browser.close()
        else:
            page = await browser.new_page()
            await page.goto(url, wait_until="domcontentloaded", timeout=30000)
            await page.wait_for_selector(".jobTuple, .jobCard", timeout=15000)
            jobs_data = await page.evaluate("""
                () => {
                    const jobs = [];
                    const cards = document.querySelectorAll('.jobTuple, .jobCard');
                    for (const card of cards) {
                        const titleEl = card.querySelector('a.title, .jobTitle a');
                        if (!titleEl) continue;
                        const title = (titleEl.textContent || '').trim();
                        const href = titleEl.getAttribute('href') || '';
                        const fullUrl = href.startsWith('/') ? 'https://www.naukri.com' + href : href;
                        const companyEl = card.querySelector('.companyName, .comp-name');
                        const locationEl = card.querySelector('.locWdth, .location');
                        const dateEl = card.querySelector('.date, .posted');
                        jobs.push({
                            title,
                            company: companyEl ? companyEl.textContent.trim() : 'Unknown',
                            location: locationEl ? locationEl.textContent.trim() : 'India',
                            url: fullUrl,
                            date: dateEl ? dateEl.textContent.trim() : '',
                        });
                        if (jobs.length >= 30) break;
                    }
                    return jobs;
                }
            """)
            await page.close()
        
        out: List[Job] = []
        for item in jobs_data:
            dt = _parse_date(item.get("date", ""))
            if not _within_days(dt, days):
                continue
            text = f"{item.get('title', '')} {item.get('company', '')}".lower()
            if query and query.lower() not in text:
                continue
            job = Job(
                id=f"naukri_{hash(item.get('url', ''))}",
                title=item.get("title", ""),
                company=item.get("company", "Unknown"),
                location=item.get("location", "India"),
                url=item.get("url", ""),
                description="",
                source="naukri",
                date=dt,
                tags=["headless"],
            )
            out.append(job)
        return out
    except Exception:
        return []


async def scrape_all(days: int = 3, query: str | None = None, enable_headless: bool = True) -> List[Job]:
    """
    Aggregate all HTTP/RSS-based scrapers in parallel.
    Optionally includes Playwright headless scrapers (slower but more comprehensive).
    
    Args:
        days: Maximum age of jobs in days
        query: Search query (e.g., "data analyst")
        enable_headless: If True and Playwright is available, run headless browser scrapers
    """
    import os
    enable_headless = enable_headless and PLAYWRIGHT_AVAILABLE and os.getenv("ENABLE_HEADLESS", "1") == "1"
    
    tasks = [
        # RSS/HTTP sources (fast, reliable)
        scrape_weworkremotely(days=days, query=query),
        scrape_jobscollider(days=days, query=query),
        scrape_remoteok(days=days, query=query),
        scrape_remotive_api(days=days, query=query),
        scrape_remotive_rss(days=days, query=query),
        scrape_wellfound(days=days, query=query),
        scrape_indeed_rss(days=days, query=query),
        scrape_remote_co(days=days, query=query),
        scrape_jobspresso(days=days, query=query),
        scrape_himalayas(days=days, query=query),
        scrape_authentic_jobs(days=days, query=query),
    ]
    
    # Add Playwright headless scrapers if enabled
    if enable_headless:
        # Use a shared browser instance for efficiency
        try:
            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=True)
                try:
                    headless_tasks = [
                        scrape_linkedin(days=days, query=query, browser=browser),
                        scrape_indeed_headless(days=days, query=query, browser=browser),
                        scrape_naukri(days=days, query=query, browser=browser),
                    ]
                    tasks.extend(headless_tasks)
                    results = await asyncio.gather(*tasks, return_exceptions=True)
                finally:
                    await browser.close()
        except Exception as e:
            print(f"Headless scraping failed: {e}")
            # If headless fails, fall back to HTTP-only
            results = await asyncio.gather(*tasks[:len(tasks)], return_exceptions=True)
    else:
        results = await asyncio.gather(*tasks, return_exceptions=True)
    
    jobs: List[Job] = []
    seen = set()
    error_count = 0
    for i, res in enumerate(results):
        if isinstance(res, Exception):
            error_count += 1
            print(f"Scraper {i} failed: {res}")
            continue
        for job in res:
            if job.url in seen:
                continue
            seen.add(job.url)
            jobs.append(job)
    
    print(f"Scraped {len(jobs)} jobs from {len(results) - error_count} sources ({error_count} errors)")
    return jobs
