from __future__ import annotations

import asyncio
import logging
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

logger = logging.getLogger(__name__)

USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"


async def fetch_text(client: httpx.AsyncClient, url: str, timeout: float = 15.0, retries: int = 2) -> str:
    """Fetch text with retries and better error handling."""
    for attempt in range(retries + 1):
        try:
            resp = await client.get(url, headers={"User-Agent": USER_AGENT}, timeout=timeout, follow_redirects=True)
            if resp.status_code == 200:
                return resp.text
            elif resp.status_code in [429, 503, 504]:  # Rate limit or service unavailable
                if attempt < retries:
                    wait_time = (attempt + 1) * 2  # Exponential backoff: 2s, 4s
                    logger.warning(f"Rate limited on {url}, retrying in {wait_time}s (attempt {attempt + 1}/{retries + 1})")
                    await asyncio.sleep(wait_time)
                    continue
            logger.warning(f"Failed to fetch {url}: HTTP {resp.status_code}")
            return ""
        except httpx.TimeoutException:
            if attempt < retries:
                logger.warning(f"Timeout fetching {url}, retrying (attempt {attempt + 1}/{retries + 1})")
                await asyncio.sleep(1)
                continue
            logger.error(f"Timeout fetching {url} after {retries + 1} attempts")
            return ""
        except Exception as e:
            if attempt < retries:
                logger.warning(f"Error fetching {url}: {e}, retrying (attempt {attempt + 1}/{retries + 1})")
                await asyncio.sleep(1)
                continue
            logger.error(f"Error fetching {url}: {e}")
            return ""
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


def _matches_query(title: str, summary: str, query: str | None) -> bool:
    """
    Very lenient matching: 
    - No query = match all
    - Generic queries like "data analyst" = match if ANY data-related keyword OR skill keyword appears
    - Specific queries = match query words OR data/skill keywords
    - Always include jobs with data/analyst/analytics/BI/science keywords regardless of query
    """
    if not query:
        return True
    
    text = f"{title} {summary}".lower()
    query_lower = query.lower().strip()
    query_words = query_lower.split()
    
    # Data/analyst keywords (always match these regardless of query)
    data_kw = [
        "data", "analyst", "analytics", "bi", "business intelligence",
        "science", "engineer", "scientist", "intelligence", "insights",
        "reporting", "metrics", "kpi", "dashboard",
    ]
    
    # Skill keywords (for skill-based matching - don't miss non-"data" roles)
    skill_kw = [
        "python", "sql", "tableau", "power bi", "looker", "visualization",
        "machine learning", "ml modeling", "statistics", "a/b testing",
        "experimentation", "reporting", "dashboards", "etl", "data pipeline",
        "pandas", "numpy", "scikit-learn", "tensorflow", "pytorch",
        "excel", "spreadsheet", "r language", "r programming",
    ]
    
    # If query is generic ("data analyst", "analyst", "data"), be very lenient
    generic_queries = ["data analyst", "analyst", "data", "analytics"]
    is_generic = any(gq in query_lower for gq in generic_queries) or len(query_words) <= 2
    
    # Always match if data/skill keywords appear (very lenient)
    if any(k in text for k in data_kw) or any(sk in text for sk in skill_kw):
        return True
    
    # If generic query, match almost everything with data context
    if is_generic:
        return True  # Very lenient for generic queries
    
    # For specific queries, match query words
    return any(w in text for w in query_words)


async def scrape_weworkremotely(days: int = 3, query: str | None = None) -> List[Job]:
    """
    Scrape WeWorkRemotely RSS feed.
    This is HTTP-only (no headless) but gives us solid remote analyst/BI roles.
    """
    url = "https://weworkremotely.com/remote-jobs.rss"
    try:
        async with httpx.AsyncClient(timeout=20.0) as client:
            xml = await fetch_text(client, url, timeout=20.0, retries=2)
        if not xml:
            logger.warning(f"Empty response from {url}")
            return []

        feed = feedparser.parse(xml)
        if feed.bozo and feed.bozo_exception:
            logger.warning(f"Feed parse error for {url}: {feed.bozo_exception}")
        
        out: List[Job] = []
        for entry in feed.entries:
            try:
                title = getattr(entry, "title", "") or ""
                link = getattr(entry, "link", "") or ""
                summary = getattr(entry, "summary", "") or ""
                published = getattr(entry, "published", "") or ""
                dt = _parse_date(published)
                if not _within_days(dt, days):
                    continue
                if not _matches_query(title, summary, query):
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
            except Exception as e:
                logger.warning(f"Error processing entry from weworkremotely: {e}")
                continue
        
        logger.info(f"Scraped {len(out)} jobs from weworkremotely")
        return out
    except Exception as e:
        logger.error(f"Error scraping weworkremotely: {e}", exc_info=True)
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
        if not _matches_query(title, summary, query):
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
        if not _matches_query(title, summary, query):
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
        title = item.get("title", "")
        desc = item.get("description_plain") or item.get("description", "")
        if not _matches_query(title, desc or "", query):
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
    Scrape Remotive RSS feed - expanded with more category feeds.
    """
    urls = [
        "https://remotive.com/feed",
        "https://remotive.com/remote-jobs/feed/data",
        "https://remotive.com/remote-jobs/feed/ai-ml",
        "https://remotive.com/remote-jobs/feed/analytics",  # Added analytics category
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
                if not _matches_query(title, summary, query):
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
    Scrape Wellfound (formerly AngelList) RSS feeds - expanded with more keyword variations.
    """
    urls = [
        "https://wellfound.com/jobs.rss?keywords=data-science&remote=true",
        "https://wellfound.com/jobs.rss?keywords=data-analyst&remote=true",
        "https://wellfound.com/jobs.rss?keywords=business-intelligence&remote=true",
        "https://wellfound.com/jobs.rss?keywords=analytics-engineer&remote=true",  # Added analytics engineer
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
                if not _matches_query(title, summary, query):
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
    Scrape Indeed RSS feed - expanded with more query variations.
    """
    search_query = query or "data analyst"
    urls = [
        f"https://rss.indeed.com/rss?q={search_query.replace(' ', '+')}&l=remote&radius=0",
        f"https://rss.indeed.com/rss?q={search_query.replace(' ', '+')}+data+scientist&l=remote&radius=0",
        f"https://rss.indeed.com/rss?q=business+analyst&l=remote&radius=0",  # Added business analyst
        f"https://rss.indeed.com/rss?q=analytics+engineer&l=remote&radius=0",  # Added analytics engineer
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
                if not _matches_query(title, summary, query):
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
        if not _matches_query(title, summary, query):
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
        if not _matches_query(title, summary, query):
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
        if not _matches_query(title, summary, query):
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


async def scrape_remotive_data_feed(days: int = 3, query: str | None = None) -> List[Job]:
    """
    Scrape Remotive Data category RSS feed.
    """
    url = "https://remotive.com/remote-jobs/feed/data"
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
        if not _matches_query(title, summary, query):
            continue
        if not link:
            continue
        job = Job(
            id=f"remotive_data_{hash(link)}",
            title=title,
            company="Unknown",
            location="Remote",
            url=link,
            description=summary,
            source="remotive_data",
            date=dt,
            tags=["rss"],
        )
        out.append(job)
    return out


async def scrape_remotive_ai_ml_feed(days: int = 3, query: str | None = None) -> List[Job]:
    """
    Scrape Remotive AI/ML category RSS feed.
    """
    url = "https://remotive.com/remote-jobs/feed/ai-ml"
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
        if not _matches_query(title, summary, query):
            continue
        if not link:
            continue
        job = Job(
            id=f"remotive_ai_ml_{hash(link)}",
            title=title,
            company="Unknown",
            location="Remote",
            url=link,
            description=summary,
            source="remotive_ai_ml",
            date=dt,
            tags=["rss"],
        )
        out.append(job)
    return out


async def scrape_stackoverflow_jobs(days: int = 3, query: str | None = None) -> List[Job]:
    """
    Scrape Stack Overflow Jobs RSS feed - expanded with more query variations.
    """
    search_query = query or "data analyst"
    urls = [
        f"https://stackoverflow.com/jobs/feed?q={search_query.replace(' ', '+')}&l=remote&d=20&u=Km",
        f"https://stackoverflow.com/jobs/feed?q=data+analyst&l=remote&d=20&u=Km",  # Explicit data analyst
    ]
    out: List[Job] = []
    seen_urls = set()  # Deduplicate across multiple URLs
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
                if not _matches_query(title, summary, query):
                    continue
                if not link:
                    continue
                # Extract company from title (Stack Overflow format: "Job Title - Company Name")
                company = "Unknown"
                if " - " in title:
                    parts = title.split(" - ", 1)
                    if len(parts) == 2:
                        title = parts[0].strip()
                        company = parts[1].strip()
                if link in seen_urls:
                    continue  # Skip duplicates
                seen_urls.add(link)
                job = Job(
                    id=f"stackoverflow_{hash(link)}",
                    title=title,
                    company=company,
                    location="Remote",
                    url=link,
                    description=summary,
                    source="stackoverflow",
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
        if not _matches_query(title, summary, query):
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

async def _retry_headless_operation(operation, max_retries: int = 2, delay: float = 2.0):
    """Helper to retry headless browser operations with exponential backoff."""
    for attempt in range(max_retries + 1):
        try:
            return await operation()
        except Exception as e:
            if attempt < max_retries:
                wait_time = delay * (2 ** attempt)  # Exponential backoff
                logger.warning(f"Headless operation failed (attempt {attempt + 1}/{max_retries + 1}): {e}, retrying in {wait_time}s")
                await asyncio.sleep(wait_time)
                continue
            logger.error(f"Headless operation failed after {max_retries + 1} attempts: {e}")
            raise
    return None


async def scrape_linkedin(days: int = 3, query: str | None = None, browser: Optional[Browser] = None, max_results: int = 200) -> List[Job]:
    """
    Scrape LinkedIn Jobs using Playwright.
    Fetches as many results as possible (up to max_results, default 200).
    Scrolls and paginates to get more results.
    Note: LinkedIn may block bots, so this may not always work.
    """
    if not PLAYWRIGHT_AVAILABLE:
        return []
    
    search_query = query or "data analyst"
    url = f"https://www.linkedin.com/jobs/search?keywords={search_query.replace(' ', '%20')}&location=remote&f_TPR=r259200&f_E=2,3&f_TP=1"
    
    try:
        should_close_browser = browser is None
        if browser is None:
            async with async_playwright() as p:
                browser = await p.chromium.launch(
                    headless=True,
                    args=['--no-sandbox', '--disable-setuid-sandbox', '--disable-dev-shm-usage']
                )
                page = await browser.new_page()
                await page.set_extra_http_headers({"User-Agent": USER_AGENT})
                
                # Navigate with retry
                async def navigate():
                    await page.goto(url, wait_until="networkidle", timeout=45000)
                    # Try multiple selectors for LinkedIn's dynamic structure
                    selectors = [
                        ".jobs-search__results-list",
                        "[data-test-id='job-card']",
                        "ul.jobs-search__results-list li",
                        ".scaffold-layout__list-container li"
                    ]
                    for selector in selectors:
                        try:
                            await page.wait_for_selector(selector, timeout=10000)
                            logger.info(f"LinkedIn: Found selector {selector}")
                            break
                        except:
                            continue
                    else:
                        logger.warning("LinkedIn: No known selectors found, proceeding anyway")
                
                await _retry_headless_operation(navigate, max_retries=1)
                
                # Scroll and paginate to get more results
                jobs_data = []
                seen_urls = set()
                scroll_attempts = 0
                max_scrolls = 10  # Scroll up to 10 times
                
                while len(jobs_data) < max_results and scroll_attempts < max_scrolls:
                    # Scroll to load more
                    await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                    await asyncio.sleep(2)  # Wait for lazy loading
                    
                    # Extract jobs from current view
                    new_jobs = await page.evaluate(f"""
                        () => {{
                            const jobs = [];
                            const cards = document.querySelectorAll('li[class*="job"], [data-test-id="job-card"]');
                            for (const card of cards) {{
                                const link = card.querySelector('a[href*="/jobs/view/"]');
                                if (!link) continue;
                                const title = (link.textContent || '').trim();
                                if (!title) continue;
                                const href = link.getAttribute('href') || '';
                                const fullUrl = href.startsWith('/') ? 'https://www.linkedin.com' + href : href;
                                
                                // Skip duplicates
                                if (jobs.some(j => j.url === fullUrl)) continue;
                                
                                const companyEl = card.querySelector('.job-search-card__subtitle, [class*="company"]');
                                const locationEl = card.querySelector('.job-search-card__location, [class*="location"]');
                                const timeEl = card.querySelector('.job-search-card__listdate, time');
                                jobs.push({{
                                    title,
                                    company: companyEl ? companyEl.textContent.trim() : 'Unknown',
                                    location: locationEl ? locationEl.textContent.trim() : 'Remote',
                                    url: fullUrl,
                                    date: timeEl ? (timeEl.getAttribute('datetime') || timeEl.textContent.trim()) : '',
                                }});
                                if (jobs.length >= {max_results}) break;
                            }}
                            return jobs;
                        }}
                    """)
                    
                    # Add new unique jobs
                    for job in new_jobs:
                        if job['url'] not in seen_urls:
                            jobs_data.append(job)
                            seen_urls.add(job['url'])
                            if len(jobs_data) >= max_results:
                                break
                    
                    scroll_attempts += 1
                    if len(new_jobs) == 0:  # No new jobs found, stop scrolling
                        break
                
                await browser.close()
        else:
            page = await browser.new_page()
            await page.set_extra_http_headers({"User-Agent": USER_AGENT})
            
            async def navigate():
                await page.goto(url, wait_until="networkidle", timeout=45000)
                selectors = [
                    ".jobs-search__results-list",
                    "[data-test-id='job-card']",
                    "ul.jobs-search__results-list li",
                    ".scaffold-layout__list-container li"
                ]
                for selector in selectors:
                    try:
                        await page.wait_for_selector(selector, timeout=10000)
                        break
                    except:
                        continue
            
            await _retry_headless_operation(navigate, max_retries=1)
            
            # Scroll and paginate
            jobs_data = []
            seen_urls = set()
            scroll_attempts = 0
            max_scrolls = 10
            
            while len(jobs_data) < max_results and scroll_attempts < max_scrolls:
                await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                await asyncio.sleep(2)
                
                new_jobs = await page.evaluate(f"""
                    () => {{
                        const jobs = [];
                        const cards = document.querySelectorAll('li[class*="job"], [data-test-id="job-card"]');
                        for (const card of cards) {{
                            const link = card.querySelector('a[href*="/jobs/view/"]');
                            if (!link) continue;
                            const title = (link.textContent || '').trim();
                            if (!title) continue;
                            const href = link.getAttribute('href') || '';
                            const fullUrl = href.startsWith('/') ? 'https://www.linkedin.com' + href : href;
                            if (jobs.some(j => j.url === fullUrl)) continue;
                            const companyEl = card.querySelector('.job-search-card__subtitle, [class*="company"]');
                            const locationEl = card.querySelector('.job-search-card__location, [class*="location"]');
                            const timeEl = card.querySelector('.job-search-card__listdate, time');
                            jobs.push({{
                                title,
                                company: companyEl ? companyEl.textContent.trim() : 'Unknown',
                                location: locationEl ? locationEl.textContent.trim() : 'Remote',
                                url: fullUrl,
                                date: timeEl ? (timeEl.getAttribute('datetime') || timeEl.textContent.trim()) : '',
                            }});
                            if (jobs.length >= {max_results}) break;
                        }}
                        return jobs;
                    }}
                """)
                
                for job in new_jobs:
                    if job['url'] not in seen_urls:
                        jobs_data.append(job)
                        seen_urls.add(job['url'])
                        if len(jobs_data) >= max_results:
                            break
                
                scroll_attempts += 1
                if len(new_jobs) == 0:
                    break
            
            await page.close()
        
        out: List[Job] = []
        for item in jobs_data:
            dt = _parse_date(item.get("date", ""))
            if not _within_days(dt, days):
                continue
            if not _matches_query(item.get("title", ""), item.get("company", ""), query):
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
        logger.info(f"Scraped {len(out)} jobs from linkedin")
        return out
    except Exception as e:
        logger.error(f"Error scraping linkedin: {e}", exc_info=True)
        return []


async def scrape_indeed_headless(days: int = 3, query: str | None = None, browser: Optional[Browser] = None, max_results: int = 200) -> List[Job]:
    """
    Scrape Indeed Jobs using Playwright (headless browser).
    Fetches as many results as possible (up to max_results, default 200).
    Scrolls and paginates through multiple pages.
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
                
                jobs_data = []
                seen_urls = set()
                page_num = 0
                max_pages = 10  # Try up to 10 pages
                
                while len(jobs_data) < max_results and page_num < max_pages:
                    # Scroll to load more
                    await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                    await asyncio.sleep(2)
                    
                    # Extract jobs
                    new_jobs = await page.evaluate(f"""
                        () => {{
                            const jobs = [];
                            const cards = document.querySelectorAll('.job_seen_beacon, .jobCard');
                            for (const card of cards) {{
                                const titleEl = card.querySelector('h2.jobTitle a, a[data-jk]');
                                if (!titleEl) continue;
                                const title = (titleEl.textContent || '').trim();
                                const href = titleEl.getAttribute('href') || '';
                                const fullUrl = href.startsWith('/') ? 'https://www.indeed.com' + href : href;
                                if (jobs.some(j => j.url === fullUrl)) continue;
                                const companyEl = card.querySelector('.companyName, [data-testid="company-name"]');
                                const locationEl = card.querySelector('.companyLocation, [data-testid="text-location"]');
                                const dateEl = card.querySelector('.date, [data-testid="myJobsStateDate"]');
                                jobs.push({{
                                    title,
                                    company: companyEl ? companyEl.textContent.trim() : 'Unknown',
                                    location: locationEl ? locationEl.textContent.trim() : 'Remote',
                                    url: fullUrl,
                                    date: dateEl ? dateEl.textContent.trim() : '',
                                }});
                                if (jobs.length >= {max_results}) break;
                            }}
                            return jobs;
                        }}
                    """)
                    
                    for job in new_jobs:
                        if job['url'] not in seen_urls:
                            jobs_data.append(job)
                            seen_urls.add(job['url'])
                            if len(jobs_data) >= max_results:
                                break
                    
                    # Try to go to next page
                    try:
                        next_button = await page.query_selector('a[aria-label="Next"]')
                        if next_button and len(jobs_data) < max_results:
                            await next_button.click()
                            await page.wait_for_selector(".job_seen_beacon, .jobCard", timeout=10000)
                            await asyncio.sleep(2)
                            page_num += 1
                        else:
                            break
                    except Exception:
                        break  # No more pages
                
                await browser.close()
        else:
            page = await browser.new_page()
            await page.goto(url, wait_until="domcontentloaded", timeout=30000)
            await page.wait_for_selector(".job_seen_beacon, .jobCard", timeout=15000)
            
            jobs_data = []
            seen_urls = set()
            page_num = 0
            max_pages = 10
            
            while len(jobs_data) < max_results and page_num < max_pages:
                await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                await asyncio.sleep(2)
                
                new_jobs = await page.evaluate(f"""
                    () => {{
                        const jobs = [];
                        const cards = document.querySelectorAll('.job_seen_beacon, .jobCard');
                        for (const card of cards) {{
                            const titleEl = card.querySelector('h2.jobTitle a, a[data-jk]');
                            if (!titleEl) continue;
                            const title = (titleEl.textContent || '').trim();
                            const href = titleEl.getAttribute('href') || '';
                            const fullUrl = href.startsWith('/') ? 'https://www.indeed.com' + href : href;
                            if (jobs.some(j => j.url === fullUrl)) continue;
                            const companyEl = card.querySelector('.companyName, [data-testid="company-name"]');
                            const locationEl = card.querySelector('.companyLocation, [data-testid="text-location"]');
                            const dateEl = card.querySelector('.date, [data-testid="myJobsStateDate"]');
                            jobs.push({{
                                title,
                                company: companyEl ? companyEl.textContent.trim() : 'Unknown',
                                location: locationEl ? locationEl.textContent.trim() : 'Remote',
                                url: fullUrl,
                                date: dateEl ? dateEl.textContent.trim() : '',
                            }});
                            if (jobs.length >= {max_results}) break;
                        }}
                        return jobs;
                    }}
                """)
                
                for job in new_jobs:
                    if job['url'] not in seen_urls:
                        jobs_data.append(job)
                        seen_urls.add(job['url'])
                        if len(jobs_data) >= max_results:
                            break
                
                try:
                    next_button = await page.query_selector('a[aria-label="Next"]')
                    if next_button and len(jobs_data) < max_results:
                        await next_button.click()
                        await page.wait_for_selector(".job_seen_beacon, .jobCard", timeout=10000)
                        await asyncio.sleep(2)
                        page_num += 1
                    else:
                        break
                except Exception:
                    break
            
            await page.close()
        
        out: List[Job] = []
        for item in jobs_data:
            dt = _parse_date(item.get("date", ""))
            if not _within_days(dt, days):
                continue
            if not _matches_query(item.get("title", ""), item.get("company", ""), query):
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


async def scrape_naukri(days: int = 3, query: str | None = None, browser: Optional[Browser] = None, max_results: int = 200) -> List[Job]:
    """
    Scrape Naukri.com (India) using Playwright.
    Fetches as many results as possible (up to max_results, default 200).
    Scrolls and paginates through multiple pages.
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
                
                jobs_data = []
                seen_urls = set()
                page_num = 0
                max_pages = 10  # Try up to 10 pages
                
                while len(jobs_data) < max_results and page_num < max_pages:
                    # Scroll to load more
                    await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                    await asyncio.sleep(2)
                    
                    # Extract jobs
                    new_jobs = await page.evaluate(f"""
                        () => {{
                            const jobs = [];
                            const cards = document.querySelectorAll('.jobTuple, .jobCard');
                            for (const card of cards) {{
                                const titleEl = card.querySelector('a.title, .jobTitle a');
                                if (!titleEl) continue;
                                const title = (titleEl.textContent || '').trim();
                                const href = titleEl.getAttribute('href') || '';
                                const fullUrl = href.startsWith('/') ? 'https://www.naukri.com' + href : href;
                                if (jobs.some(j => j.url === fullUrl)) continue;
                                const companyEl = card.querySelector('.companyName, .comp-name');
                                const locationEl = card.querySelector('.locWdth, .location');
                                const dateEl = card.querySelector('.date, .posted');
                                jobs.push({{
                                    title,
                                    company: companyEl ? companyEl.textContent.trim() : 'Unknown',
                                    location: locationEl ? locationEl.textContent.trim() : 'India',
                                    url: fullUrl,
                                    date: dateEl ? dateEl.textContent.trim() : '',
                                }});
                                if (jobs.length >= {max_results}) break;
                            }}
                            return jobs;
                        }}
                    """)
                    
                    for job in new_jobs:
                        if job['url'] not in seen_urls:
                            jobs_data.append(job)
                            seen_urls.add(job['url'])
                            if len(jobs_data) >= max_results:
                                break
                    
                    # Try to go to next page
                    try:
                        next_button = await page.query_selector('a[class*="next"], a[title*="Next"]')
                        if next_button and len(jobs_data) < max_results:
                            await next_button.click()
                            await page.wait_for_selector(".jobTuple, .jobCard", timeout=10000)
                            await asyncio.sleep(2)
                            page_num += 1
                        else:
                            break
                    except Exception:
                        break  # No more pages
                
                await browser.close()
        else:
            page = await browser.new_page()
            await page.goto(url, wait_until="domcontentloaded", timeout=30000)
            await page.wait_for_selector(".jobTuple, .jobCard", timeout=15000)
            
            jobs_data = []
            seen_urls = set()
            page_num = 0
            max_pages = 10
            
            while len(jobs_data) < max_results and page_num < max_pages:
                await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                await asyncio.sleep(2)
                
                new_jobs = await page.evaluate(f"""
                    () => {{
                        const jobs = [];
                        const cards = document.querySelectorAll('.jobTuple, .jobCard');
                        for (const card of cards) {{
                            const titleEl = card.querySelector('a.title, .jobTitle a');
                            if (!titleEl) continue;
                            const title = (titleEl.textContent || '').trim();
                            const href = titleEl.getAttribute('href') || '';
                            const fullUrl = href.startsWith('/') ? 'https://www.naukri.com' + href : href;
                            if (jobs.some(j => j.url === fullUrl)) continue;
                            const companyEl = card.querySelector('.companyName, .comp-name');
                            const locationEl = card.querySelector('.locWdth, .location');
                            const dateEl = card.querySelector('.date, .posted');
                            jobs.push({{
                                title,
                                company: companyEl ? companyEl.textContent.trim() : 'Unknown',
                                location: locationEl ? locationEl.textContent.trim() : 'India',
                                url: fullUrl,
                                date: dateEl ? dateEl.textContent.trim() : '',
                            }});
                            if (jobs.length >= {max_results}) break;
                        }}
                        return jobs;
                    }}
                """)
                
                for job in new_jobs:
                    if job['url'] not in seen_urls:
                        jobs_data.append(job)
                        seen_urls.add(job['url'])
                        if len(jobs_data) >= max_results:
                            break
                
                try:
                    next_button = await page.query_selector('a[class*="next"], a[title*="Next"]')
                    if next_button and len(jobs_data) < max_results:
                        await next_button.click()
                        await page.wait_for_selector(".jobTuple, .jobCard", timeout=10000)
                        await asyncio.sleep(2)
                        page_num += 1
                    else:
                        break
                except Exception:
                    break
            
            await page.close()
        
        out: List[Job] = []
        for item in jobs_data:
            dt = _parse_date(item.get("date", ""))
            if not _within_days(dt, days):
                continue
            if not _matches_query(item.get("title", ""), item.get("company", ""), query):
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


async def scrape_hirist(days: int = 3, query: str | None = None, browser: Optional[Browser] = None, max_results: int = 200) -> List[Job]:
    """
    Scrape Hirist.com (India) using Playwright.
    Fetches as many results as possible (up to max_results, default 200).
    """
    if not PLAYWRIGHT_AVAILABLE:
        return []
    
    search_query = query or "data analyst"
    slug = search_query.lower().replace(" ", "-")
    url = f"https://hirist.com/jobs/{slug}-jobs"
    
    try:
        if browser is None:
            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=True)
                page = await browser.new_page()
                await page.goto(url, wait_until="domcontentloaded", timeout=30000)
                await page.wait_for_selector(".job-card, .job-item, [data-job-id], a[href*='/job/']", timeout=15000)
                
                jobs_data = []
                seen_urls = set()
                scroll_attempts = 0
                max_scrolls = 10
                
                while len(jobs_data) < max_results and scroll_attempts < max_scrolls:
                    await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                    await asyncio.sleep(2)
                    
                    new_jobs = await page.evaluate(f"""
                        () => {{
                            const jobs = [];
                            const cards = document.querySelectorAll('.job-card, .job-item, [data-job-id]');
                            if (cards.length === 0) {{
                                const links = document.querySelectorAll('a[href*="/job/"]');
                                links.forEach((a) => {{
                                    const title = (a.textContent || '').trim();
                                    if (title.length < 5) return;
                                    const href = a.getAttribute('href') || '';
                                    const url = href.startsWith('http') ? href : 'https://hirist.com' + href;
                                    const row = a.closest('tr, .row, li, div[class*="card"]');
                                    const companyEl = row ? row.querySelector('.company-name, .company, [class*="company"]') : null;
                                    if (!jobs.some(j => j.url === url)) {{
                                        jobs.push({{
                                            title,
                                            company: companyEl ? companyEl.textContent.trim() : 'Unknown',
                                            location: 'India',
                                            url,
                                            date: '',
                                        }});
                                    }}
                                }});
                            }} else {{
                                for (const card of cards) {{
                                    const link = card.querySelector('a[href*="/job/"]');
                                    if (!link) continue;
                                    const title = (link.textContent || '').trim();
                                    if (!title) continue;
                                    const href = link.getAttribute('href') || '';
                                    const fullUrl = href.startsWith('http') ? href : 'https://hirist.com' + href;
                                    if (jobs.some(j => j.url === fullUrl)) continue;
                                    const companyEl = card.querySelector('.company-name, [class*="company"]');
                                    jobs.push({{
                                        title,
                                        company: companyEl ? companyEl.textContent.trim() : 'Unknown',
                                        location: 'India',
                                        url: fullUrl,
                                        date: '',
                                    }});
                                    if (jobs.length >= {max_results}) break;
                                }}
                            }}
                            return jobs;
                        }}
                    """)
                    
                    for job in new_jobs:
                        if job['url'] not in seen_urls:
                            jobs_data.append(job)
                            seen_urls.add(job['url'])
                            if len(jobs_data) >= max_results:
                                break
                    
                    scroll_attempts += 1
                    if len(new_jobs) == 0:
                        break
                
                await browser.close()
        else:
            page = await browser.new_page()
            await page.goto(url, wait_until="domcontentloaded", timeout=30000)
            await page.wait_for_selector(".job-card, .job-item, [data-job-id], a[href*='/job/']", timeout=15000)
            
            jobs_data = []
            seen_urls = set()
            scroll_attempts = 0
            max_scrolls = 10
            
            while len(jobs_data) < max_results and scroll_attempts < max_scrolls:
                await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                await asyncio.sleep(2)
                
                new_jobs = await page.evaluate(f"""
                    () => {{
                        const jobs = [];
                        const cards = document.querySelectorAll('.job-card, .job-item, [data-job-id]');
                        if (cards.length === 0) {{
                            const links = document.querySelectorAll('a[href*="/job/"]');
                            links.forEach((a) => {{
                                const title = (a.textContent || '').trim();
                                if (title.length < 5) return;
                                const href = a.getAttribute('href') || '';
                                const url = href.startsWith('http') ? href : 'https://hirist.com' + href;
                                const row = a.closest('tr, .row, li, div[class*="card"]');
                                const companyEl = row ? row.querySelector('.company-name, .company, [class*="company"]') : null;
                                if (!jobs.some(j => j.url === url)) {{
                                    jobs.push({{
                                        title,
                                        company: companyEl ? companyEl.textContent.trim() : 'Unknown',
                                        location: 'India',
                                        url,
                                        date: '',
                                    }});
                                }}
                            }});
                        }} else {{
                            for (const card of cards) {{
                                const link = card.querySelector('a[href*="/job/"]');
                                if (!link) continue;
                                const title = (link.textContent || '').trim();
                                if (!title) continue;
                                const href = link.getAttribute('href') || '';
                                const fullUrl = href.startsWith('http') ? href : 'https://hirist.com' + href;
                                if (jobs.some(j => j.url === fullUrl)) continue;
                                const companyEl = card.querySelector('.company-name, [class*="company"]');
                                jobs.push({{
                                    title,
                                    company: companyEl ? companyEl.textContent.trim() : 'Unknown',
                                    location: 'India',
                                    url: fullUrl,
                                    date: '',
                                }});
                                if (jobs.length >= {max_results}) break;
                            }}
                        }}
                        return jobs;
                    }}
                """)
                
                for job in new_jobs:
                    if job['url'] not in seen_urls:
                        jobs_data.append(job)
                        seen_urls.add(job['url'])
                        if len(jobs_data) >= max_results:
                            break
                
                scroll_attempts += 1
                if len(new_jobs) == 0:
                    break
            
            await page.close()
        
        out: List[Job] = []
        for item in jobs_data:
            dt = _parse_date(item.get("date", ""))
            if dt and not _within_days(dt, days):
                continue
            if not _matches_query(item.get("title", ""), item.get("company", ""), query):
                continue
            job = Job(
                id=f"hirist_{hash(item.get('url', ''))}",
                title=item.get("title", ""),
                company=item.get("company", "Unknown"),
                location=item.get("location", "India"),
                url=item.get("url", ""),
                description="",
                source="hirist",
                date=dt,
                tags=["headless"],
            )
            out.append(job)
        return out
    except Exception as e:
        print(f"Error scraping hirist: {e}")
        return []


async def scrape_foundit(days: int = 3, query: str | None = None, browser: Optional[Browser] = None, max_results: int = 200) -> List[Job]:
    """
    Scrape Foundit.in (India) using Playwright.
    Fetches as many results as possible (up to max_results, default 200).
    """
    if not PLAYWRIGHT_AVAILABLE:
        return []
    
    search_query = query or "data analyst"
    url = f"https://www.foundit.in/search/data-analyst-jobs?query={search_query.replace(' ', '%20')}"
    
    try:
        if browser is None:
            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=True)
                page = await browser.new_page()
                await page.goto(url, wait_until="domcontentloaded", timeout=30000)
                await page.wait_for_selector(".jobCard, .job-item", timeout=15000)
                
                jobs_data = []
                seen_urls = set()
                page_num = 0
                max_pages = 10
                
                while len(jobs_data) < max_results and page_num < max_pages:
                    await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                    await asyncio.sleep(2)
                    
                    new_jobs = await page.evaluate(f"""
                        () => {{
                            const jobs = [];
                            const cards = document.querySelectorAll('.jobCard, .job-item');
                            for (const card of cards) {{
                                const link = card.querySelector('a[href*="/job/"]');
                                if (!link) continue;
                                const title = (link.textContent || '').trim();
                                if (!title) continue;
                                const href = link.getAttribute('href') || '';
                                const fullUrl = href.startsWith('/') ? 'https://www.foundit.in' + href : href;
                                if (jobs.some(j => j.url === fullUrl)) continue;
                                const companyEl = card.querySelector('.company-name, [class*="company"]');
                                const locEl = card.querySelector('.location, [class*="loc"]');
                                const timeEl = card.querySelector('.posted-date, [class*="date"]');
                                jobs.push({{
                                    title,
                                    company: companyEl ? companyEl.textContent.trim() : 'Unknown',
                                    location: locEl ? locEl.textContent.trim() : 'India',
                                    url: fullUrl,
                                    date: timeEl ? timeEl.textContent.trim() : '',
                                }});
                                if (jobs.length >= {max_results}) break;
                            }}
                            return jobs;
                        }}
                    """)
                    
                    for job in new_jobs:
                        if job['url'] not in seen_urls:
                            jobs_data.append(job)
                            seen_urls.add(job['url'])
                            if len(jobs_data) >= max_results:
                                break
                    
                    try:
                        next_button = await page.query_selector('a[class*="next"], button[class*="next"]')
                        if next_button and len(jobs_data) < max_results:
                            await next_button.click()
                            await page.wait_for_selector(".jobCard, .job-item", timeout=10000)
                            await asyncio.sleep(2)
                            page_num += 1
                        else:
                            break
                    except Exception:
                        break
                
                await browser.close()
        else:
            page = await browser.new_page()
            await page.goto(url, wait_until="domcontentloaded", timeout=30000)
            await page.wait_for_selector(".jobCard, .job-item", timeout=15000)
            
            jobs_data = []
            seen_urls = set()
            page_num = 0
            max_pages = 10
            
            while len(jobs_data) < max_results and page_num < max_pages:
                await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                await asyncio.sleep(2)
                
                new_jobs = await page.evaluate(f"""
                    () => {{
                        const jobs = [];
                        const cards = document.querySelectorAll('.jobCard, .job-item');
                        for (const card of cards) {{
                            const link = card.querySelector('a[href*="/job/"]');
                            if (!link) continue;
                            const title = (link.textContent || '').trim();
                            if (!title) continue;
                            const href = link.getAttribute('href') || '';
                            const fullUrl = href.startsWith('/') ? 'https://www.foundit.in' + href : href;
                            if (jobs.some(j => j.url === fullUrl)) continue;
                            const companyEl = card.querySelector('.company-name, [class*="company"]');
                            const locEl = card.querySelector('.location, [class*="loc"]');
                            const timeEl = card.querySelector('.posted-date, [class*="date"]');
                            jobs.push({{
                                title,
                                company: companyEl ? companyEl.textContent.trim() : 'Unknown',
                                location: locEl ? locEl.textContent.trim() : 'India',
                                url: fullUrl,
                                date: timeEl ? timeEl.textContent.trim() : '',
                            }});
                            if (jobs.length >= {max_results}) break;
                        }}
                        return jobs;
                    }}
                """)
                
                for job in new_jobs:
                    if job['url'] not in seen_urls:
                        jobs_data.append(job)
                        seen_urls.add(job['url'])
                        if len(jobs_data) >= max_results:
                            break
                
                try:
                    next_button = await page.query_selector('a[class*="next"], button[class*="next"]')
                    if next_button and len(jobs_data) < max_results:
                        await next_button.click()
                        await page.wait_for_selector(".jobCard, .job-item", timeout=10000)
                        await asyncio.sleep(2)
                        page_num += 1
                    else:
                        break
                except Exception:
                    break
            
            await page.close()
        
        out: List[Job] = []
        for item in jobs_data:
            dt = _parse_date(item.get("date", ""))
            if dt and not _within_days(dt, days):
                continue
            if not _matches_query(item.get("title", ""), item.get("company", ""), query):
                continue
            job = Job(
                id=f"foundit_{hash(item.get('url', ''))}",
                title=item.get("title", ""),
                company=item.get("company", "Unknown"),
                location=item.get("location", "India"),
                url=item.get("url", ""),
                description="",
                source="foundit",
                date=dt,
                tags=["headless"],
            )
            out.append(job)
        return out
    except Exception as e:
        print(f"Error scraping foundit: {e}")
        return []


async def scrape_shine(days: int = 3, query: str | None = None, browser: Optional[Browser] = None, max_results: int = 200) -> List[Job]:
    """
    Scrape Shine.com (India) using Playwright.
    Fetches as many results as possible (up to max_results, default 200).
    """
    if not PLAYWRIGHT_AVAILABLE:
        return []

    search_query = query or "data analyst"
    slug = search_query.lower().replace(" ", "-")
    url = f"https://www.shine.com/job-search/{slug}-jobs"

    try:
        if browser is None:
            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=True)
                page = await browser.new_page()
                await page.goto(url, wait_until="domcontentloaded", timeout=30000)
                await page.wait_for_selector(".jobCard, .job-listing, [class*='job-card']", timeout=15000)

                jobs_data = []
                seen_urls = set()
                page_num = 0
                max_pages = 10

                while len(jobs_data) < max_results and page_num < max_pages:
                    await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                    await asyncio.sleep(2)

                    new_jobs = await page.evaluate(f"""
                        () => {{
                            const jobs = [];
                            const cards = document.querySelectorAll('.jobCard, .job-listing, [class*="job-card"]');
                            for (const card of cards) {{
                                const link = card.querySelector('a[href*="/job/"]');
                                if (!link) continue;
                                const title = (link.textContent || '').trim();
                                if (!title) continue;
                                const href = link.getAttribute('href') || '';
                                const fullUrl = href.startsWith('/') ? 'https://www.shine.com' + href : href;
                                if (jobs.some(j => j.url === fullUrl)) continue;
                                const companyEl = card.querySelector('.company-name, [class*="company"]');
                                const locEl = card.querySelector('.location, [class*="loc"]');
                                const timeEl = card.querySelector('.posted-date, [class*="date"]');
                                jobs.push({{
                                    title,
                                    company: companyEl ? companyEl.textContent.trim() : 'Unknown',
                                    location: locEl ? locEl.textContent.trim() : 'India',
                                    url: fullUrl,
                                    date: timeEl ? timeEl.textContent.trim() : '',
                                }});
                                if (jobs.length >= {max_results}) break;
                            }}
                            return jobs;
                        }}
                    """)

                    for job in new_jobs:
                        if job["url"] not in seen_urls:
                            jobs_data.append(job)
                            seen_urls.add(job["url"])
                            if len(jobs_data) >= max_results:
                                break

                    try:
                        next_button = await page.query_selector('a[class*="next"], button[class*="next"]')
                        if next_button and len(jobs_data) < max_results:
                            await next_button.click()
                            await page.wait_for_selector(".jobCard, .job-listing, [class*='job-card']", timeout=10000)
                            await asyncio.sleep(2)
                            page_num += 1
                        else:
                            break
                    except Exception:
                        break

                await browser.close()
        else:
            page = await browser.new_page()
            await page.goto(url, wait_until="domcontentloaded", timeout=30000)
            await page.wait_for_selector(".jobCard, .job-listing, [class*='job-card']", timeout=15000)

            jobs_data = []
            seen_urls = set()
            page_num = 0
            max_pages = 10

            while len(jobs_data) < max_results and page_num < max_pages:
                await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                await asyncio.sleep(2)

                new_jobs = await page.evaluate(f"""
                    () => {{
                        const jobs = [];
                        const cards = document.querySelectorAll('.jobCard, .job-listing, [class*="job-card"]');
                        for (const card of cards) {{
                            const link = card.querySelector('a[href*="/job/"]');
                            if (!link) continue;
                            const title = (link.textContent || '').trim();
                            if (!title) continue;
                            const href = link.getAttribute('href') || '';
                            const fullUrl = href.startsWith('/') ? 'https://www.shine.com' + href : href;
                            if (jobs.some(j => j.url === fullUrl)) continue;
                            const companyEl = card.querySelector('.company-name, [class*="company"]');
                            const locEl = card.querySelector('.location, [class*="loc"]');
                            const timeEl = card.querySelector('.posted-date, [class*="date"]');
                            jobs.push({{
                                title,
                                company: companyEl ? companyEl.textContent.trim() : 'Unknown',
                                location: locEl ? locEl.textContent.trim() : 'India',
                                url: fullUrl,
                                date: timeEl ? timeEl.textContent.trim() : '',
                            }});
                            if (jobs.length >= {max_results}) break;
                        }}
                        return jobs;
                    }}
                """)

                for job in new_jobs:
                    if job["url"] not in seen_urls:
                        jobs_data.append(job)
                        seen_urls.add(job["url"])
                        if len(jobs_data) >= max_results:
                            break

                try:
                    next_button = await page.query_selector('a[class*="next"], button[class*="next"]')
                    if next_button and len(jobs_data) < max_results:
                        await next_button.click()
                        await page.wait_for_selector(".jobCard, .job-listing, [class*='job-card']", timeout=10000)
                        await asyncio.sleep(2)
                        page_num += 1
                    else:
                        break
                except Exception:
                    break

            await page.close()

        out: List[Job] = []
        for item in jobs_data:
            dt = _parse_date(item.get("date", ""))
            if dt and not _within_days(dt, days):
                continue
            if not _matches_query(item.get("title", ""), item.get("company", ""), query):
                continue
            job = Job(
                id=f"shine_{hash(item.get('url', ''))}",
                title=item.get("title", ""),
                company=item.get("company", "Unknown"),
                location=item.get("location", "India"),
                url=item.get("url", ""),
                description="",
                source="shine",
                date=dt,
                tags=["headless"],
            )
            out.append(job)
        return out
    except Exception as e:
        print(f"Error scraping shine: {e}")
        return []


async def scrape_monster(days: int = 3, query: str | None = None, browser: Optional[Browser] = None, max_results: int = 200) -> List[Job]:
    """
    Scrape Monster.com using Playwright.
    Fetches as many results as possible (up to max_results, default 200).
    """
    if not PLAYWRIGHT_AVAILABLE:
        return []
    
    search_query = query or "data analyst"
    url = f"https://www.monster.com/jobs/search/?q={search_query.replace(' ', '+')}&where=remote&postedDate=3"
    
    try:
        if browser is None:
            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=True)
                page = await browser.new_page()
                await page.goto(url, wait_until="domcontentloaded", timeout=30000)
                await page.wait_for_selector(".results-card, [data-test-id='job-card']", timeout=15000)
                
                jobs_data = []
                seen_urls = set()
                page_num = 0
                max_pages = 10
                
                while len(jobs_data) < max_results and page_num < max_pages:
                    await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                    await asyncio.sleep(2)
                    
                    new_jobs = await page.evaluate(f"""
                        () => {{
                            const jobs = [];
                            const cards = document.querySelectorAll('.results-card, [data-test-id="job-card"]');
                            for (const card of cards) {{
                                const link = card.querySelector('a[href*="/job/"]');
                                if (!link) continue;
                                const title = (link.textContent || '').trim();
                                if (!title) continue;
                                const href = link.getAttribute('href') || '';
                                const fullUrl = href.startsWith('/') ? 'https://www.monster.com' + href : href;
                                if (jobs.some(j => j.url === fullUrl)) continue;
                                const companyEl = card.querySelector('.company, [class*="company"]');
                                const locEl = card.querySelector('.location, [class*="location"]');
                                const timeEl = card.querySelector('.posted, [class*="posted"]');
                                jobs.push({{
                                    title,
                                    company: companyEl ? companyEl.textContent.trim() : 'Unknown',
                                    location: locEl ? locEl.textContent.trim() : '',
                                    url: fullUrl,
                                    date: timeEl ? timeEl.textContent.trim() : '',
                                }});
                                if (jobs.length >= {max_results}) break;
                            }}
                            return jobs;
                        }}
                    """)
                    
                    for job in new_jobs:
                        if job['url'] not in seen_urls:
                            jobs_data.append(job)
                            seen_urls.add(job['url'])
                            if len(jobs_data) >= max_results:
                                break
                    
                    try:
                        next_button = await page.query_selector('a[aria-label="Next"], button[aria-label="Next"]')
                        if next_button and len(jobs_data) < max_results:
                            await next_button.click()
                            await page.wait_for_selector(".results-card, [data-test-id='job-card']", timeout=10000)
                            await asyncio.sleep(2)
                            page_num += 1
                        else:
                            break
                    except Exception:
                        break
                
                await browser.close()
        else:
            page = await browser.new_page()
            await page.goto(url, wait_until="domcontentloaded", timeout=30000)
            await page.wait_for_selector(".results-card, [data-test-id='job-card']", timeout=15000)
            
            jobs_data = []
            seen_urls = set()
            page_num = 0
            max_pages = 10
            
            while len(jobs_data) < max_results and page_num < max_pages:
                await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                await asyncio.sleep(2)
                
                new_jobs = await page.evaluate(f"""
                    () => {{
                        const jobs = [];
                        const cards = document.querySelectorAll('.results-card, [data-test-id="job-card"]');
                        for (const card of cards) {{
                            const link = card.querySelector('a[href*="/job/"]');
                            if (!link) continue;
                            const title = (link.textContent || '').trim();
                            if (!title) continue;
                            const href = link.getAttribute('href') || '';
                            const fullUrl = href.startsWith('/') ? 'https://www.monster.com' + href : href;
                            if (jobs.some(j => j.url === fullUrl)) continue;
                            const companyEl = card.querySelector('.company, [class*="company"]');
                            const locEl = card.querySelector('.location, [class*="location"]');
                            const timeEl = card.querySelector('.posted, [class*="posted"]');
                            jobs.push({{
                                title,
                                company: companyEl ? companyEl.textContent.trim() : 'Unknown',
                                location: locEl ? locEl.textContent.trim() : '',
                                url: fullUrl,
                                date: timeEl ? timeEl.textContent.trim() : '',
                            }});
                            if (jobs.length >= {max_results}) break;
                        }}
                        return jobs;
                    }}
                """)
                
                for job in new_jobs:
                    if job['url'] not in seen_urls:
                        jobs_data.append(job)
                        seen_urls.add(job['url'])
                        if len(jobs_data) >= max_results:
                            break
                
                try:
                    next_button = await page.query_selector('a[aria-label="Next"], button[aria-label="Next"]')
                    if next_button and len(jobs_data) < max_results:
                        await next_button.click()
                        await page.wait_for_selector(".results-card, [data-test-id='job-card']", timeout=10000)
                        await asyncio.sleep(2)
                        page_num += 1
                    else:
                        break
                except Exception:
                    break
            
            await page.close()
        
        out: List[Job] = []
        for item in jobs_data:
            dt = _parse_date(item.get("date", ""))
            if dt and not _within_days(dt, days):
                continue
            if not _matches_query(item.get("title", ""), item.get("company", ""), query):
                continue
            job = Job(
                id=f"monster_{hash(item.get('url', ''))}",
                title=item.get("title", ""),
                company=item.get("company", "Unknown"),
                location=item.get("location", "Remote"),
                url=item.get("url", ""),
                description="",
                source="monster",
                date=dt,
                tags=["headless"],
            )
            out.append(job)
        return out
    except Exception as e:
        print(f"Error scraping monster: {e}")
        return []


async def scrape_glassdoor(days: int = 3, query: str | None = None, browser: Optional[Browser] = None, max_results: int = 200) -> List[Job]:
    """
    Scrape Glassdoor.com using Playwright.
    Fetches as many results as possible (up to max_results, default 200).
    """
    if not PLAYWRIGHT_AVAILABLE:
        return []
    
    search_query = query or "data analyst"
    url = f"https://www.glassdoor.com/Job/jobs.htm?suggestCount=0&suggestChosen=false&clickSource=searchBtn&typedKeyword={search_query.replace(' ', '+')}&sc.keyword={search_query.replace(' ', '+')}&locT=C&locId=1147401&jobType=&fromAge=3"
    
    try:
        if browser is None:
            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=True)
                page = await browser.new_page()
                await page.goto(url, wait_until="domcontentloaded", timeout=30000)
                await page.wait_for_selector(".react-job-listing, [data-test='job-listing']", timeout=15000)
                
                jobs_data = []
                seen_urls = set()
                page_num = 0
                max_pages = 10
                
                while len(jobs_data) < max_results and page_num < max_pages:
                    await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                    await asyncio.sleep(2)
                    
                    new_jobs = await page.evaluate(f"""
                        () => {{
                            const jobs = [];
                            const cards = document.querySelectorAll('.react-job-listing, [data-test="job-listing"]');
                            for (const card of cards) {{
                                const link = card.querySelector('a[href*="/partner/"], a[href*="/Job/"]');
                                if (!link) continue;
                                const title = (link.textContent || '').trim();
                                if (!title) continue;
                                const href = link.getAttribute('href') || '';
                                const fullUrl = href.startsWith('/') ? 'https://www.glassdoor.com' + href : href;
                                if (jobs.some(j => j.url === fullUrl)) continue;
                                const companyEl = card.querySelector('.job-search-key-lmzjyg, [class*="company"]');
                                const locEl = card.querySelector('.job-search-key-1m2z0jx, [class*="location"]');
                                const timeEl = card.querySelector('.job-search-key-1erf0ry, [class*="date"]');
                                jobs.push({{
                                    title,
                                    company: companyEl ? companyEl.textContent.trim() : 'Unknown',
                                    location: locEl ? locEl.textContent.trim() : '',
                                    url: fullUrl,
                                    date: timeEl ? timeEl.textContent.trim() : '',
                                }});
                                if (jobs.length >= {max_results}) break;
                            }}
                            return jobs;
                        }}
                    """)
                    
                    for job in new_jobs:
                        if job['url'] not in seen_urls:
                            jobs_data.append(job)
                            seen_urls.add(job['url'])
                            if len(jobs_data) >= max_results:
                                break
                    
                    try:
                        next_button = await page.query_selector('button[aria-label="Next"], a[aria-label="Next"]')
                        if next_button and len(jobs_data) < max_results:
                            await next_button.click()
                            await page.wait_for_selector(".react-job-listing, [data-test='job-listing']", timeout=10000)
                            await asyncio.sleep(2)
                            page_num += 1
                        else:
                            break
                    except Exception:
                        break
                
                await browser.close()
        else:
            page = await browser.new_page()
            await page.goto(url, wait_until="domcontentloaded", timeout=30000)
            await page.wait_for_selector(".react-job-listing, [data-test='job-listing']", timeout=15000)
            
            jobs_data = []
            seen_urls = set()
            page_num = 0
            max_pages = 10
            
            while len(jobs_data) < max_results and page_num < max_pages:
                await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                await asyncio.sleep(2)
                
                new_jobs = await page.evaluate(f"""
                    () => {{
                        const jobs = [];
                        const cards = document.querySelectorAll('.react-job-listing, [data-test="job-listing"]');
                        for (const card of cards) {{
                            const link = card.querySelector('a[href*="/partner/"], a[href*="/Job/"]');
                            if (!link) continue;
                            const title = (link.textContent || '').trim();
                            if (!title) continue;
                            const href = link.getAttribute('href') || '';
                            const fullUrl = href.startsWith('/') ? 'https://www.glassdoor.com' + href : href;
                            if (jobs.some(j => j.url === fullUrl)) continue;
                            const companyEl = card.querySelector('.job-search-key-lmzjyg, [class*="company"]');
                            const locEl = card.querySelector('.job-search-key-1m2z0jx, [class*="location"]');
                            const timeEl = card.querySelector('.job-search-key-1erf0ry, [class*="date"]');
                            jobs.push({{
                                title,
                                company: companyEl ? companyEl.textContent.trim() : 'Unknown',
                                location: locEl ? locEl.textContent.trim() : '',
                                url: fullUrl,
                                date: timeEl ? timeEl.textContent.trim() : '',
                            }});
                            if (jobs.length >= {max_results}) break;
                        }}
                        return jobs;
                    }}
                """)
                
                for job in new_jobs:
                    if job['url'] not in seen_urls:
                        jobs_data.append(job)
                        seen_urls.add(job['url'])
                        if len(jobs_data) >= max_results:
                            break
                
                try:
                    next_button = await page.query_selector('button[aria-label="Next"], a[aria-label="Next"]')
                    if next_button and len(jobs_data) < max_results:
                        await next_button.click()
                        await page.wait_for_selector(".react-job-listing, [data-test='job-listing']", timeout=10000)
                        await asyncio.sleep(2)
                        page_num += 1
                    else:
                        break
                except Exception:
                    break
            
            await page.close()
        
        out: List[Job] = []
        for item in jobs_data:
            dt = _parse_date(item.get("date", ""))
            if dt and not _within_days(dt, days):
                continue
            if not _matches_query(item.get("title", ""), item.get("company", ""), query):
                continue
            job = Job(
                id=f"glassdoor_{hash(item.get('url', ''))}",
                title=item.get("title", ""),
                company=item.get("company", "Unknown"),
                location=item.get("location", "Remote"),
                url=item.get("url", ""),
                description="",
                source="glassdoor",
                date=dt,
                tags=["headless"],
            )
            out.append(job)
        return out
    except Exception as e:
        print(f"Error scraping glassdoor: {e}")
        return []


async def scrape_all(
    days: int = 3,
    query: str | None = None,
    enable_headless: bool = True,
    mode: str = "all",
) -> List[Job]:
    """
    Aggregate all HTTP/RSS-based scrapers in parallel.
    Optionally includes Playwright headless scrapers (slower but more comprehensive).
    
    Args:
        days: Maximum age of jobs in days
        query: Search query (e.g., "data analyst")
        enable_headless: If True and Playwright is available, run headless browser scrapers
    """
    import os
    from .jobspy_integration import scrape_jobspy_sources

    enable_headless = enable_headless and PLAYWRIGHT_AVAILABLE and os.getenv("ENABLE_HEADLESS", "1") == "1"
    use_jobspy = os.getenv("USE_JOBSPY", "0") == "1"
    mode = (mode or "all").lower()
    # Optional cap for Railway free tier (e.g. set MAX_SCRAPER_SOURCES=12 to run only 12 sources)
    max_sources_raw = os.getenv("MAX_SCRAPER_SOURCES", "")
    max_sources = int(max_sources_raw) if max_sources_raw.isdigit() else None

    tasks = []

    # RSS/HTTP sources (fast, reliable)
    if mode in ("rss", "all"):
        rss_tasks = [
            [
                scrape_weworkremotely(days=days, query=query),
                scrape_jobscollider(days=days, query=query),
                scrape_remoteok(days=days, query=query),
                scrape_remotive_api(days=days, query=query),
                scrape_remotive_rss(days=days, query=query),
                scrape_remotive_data_feed(days=days, query=query),  # Remotive data category
                scrape_remotive_ai_ml_feed(days=days, query=query),  # Remotive AI/ML category
                scrape_wellfound(days=days, query=query),
                scrape_indeed_rss(days=days, query=query),
                scrape_remote_co(days=days, query=query),
                scrape_jobspresso(days=days, query=query),
                scrape_himalayas(days=days, query=query),
                scrape_authentic_jobs(days=days, query=query),
                scrape_stackoverflow_jobs(days=days, query=query),  # Stack Overflow Jobs RSS
        ]
        if max_sources is not None:
            rss_tasks = rss_tasks[:max_sources]
        tasks.extend(rss_tasks)

    # Optional: python-jobspy backend for big job boards (LinkedIn, Indeed, Glassdoor, ZipRecruiter)
    if use_jobspy and mode in ("headless", "all"):
        tasks.append(scrape_jobspy_sources(days=days, query=query))

    # Add Playwright headless scrapers if enabled and requested
    if enable_headless and mode in ("headless", "all"):
        # Use a shared browser instance for efficiency
        try:
            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=True)
                try:
                    headless_tasks = [
                        scrape_linkedin(days=days, query=query, browser=browser),
                        scrape_indeed_headless(days=days, query=query, browser=browser),
                        scrape_naukri(days=days, query=query, browser=browser),
                        scrape_hirist(days=days, query=query, browser=browser),
                        scrape_foundit(days=days, query=query, browser=browser),
                        scrape_shine(days=days, query=query, browser=browser),
                        scrape_monster(days=days, query=query, browser=browser),
                        scrape_glassdoor(days=days, query=query, browser=browser),
                    ]
                    tasks.extend(headless_tasks)
                    if max_sources is not None:
                        tasks = tasks[:max_sources]
                    results = await asyncio.gather(*tasks, return_exceptions=True)
                finally:
                    await browser.close()
        except Exception as e:
            logger.error(f"Headless scraping failed: {e}", exc_info=True)
            # If headless fails, fall back to HTTP-only
            if max_sources is not None:
                tasks = tasks[:max_sources]
            results = await asyncio.gather(*tasks, return_exceptions=True)
    else:
        if max_sources is not None:
            tasks = tasks[:max_sources]
        results = await asyncio.gather(*tasks, return_exceptions=True)
    
    jobs: List[Job] = []
    seen = set()
    error_count = 0
    source_counts = {}
    
    for i, res in enumerate(results):
        if isinstance(res, Exception):
            error_count += 1
            logger.warning(f"Scraper {i} failed: {res}")
            continue
        if not isinstance(res, list):
            logger.warning(f"Scraper {i} returned non-list: {type(res)}")
            continue
        
        source_name = res[0].source if res and len(res) > 0 else f"scraper_{i}"
        source_counts[source_name] = len(res)
        
        for job in res:
            if job.url in seen:
                continue
            seen.add(job.url)
            
            # Enhance job with metadata (YOE, visa, salary, currency)
            try:
                from .scoring import enhance_job_with_metadata, calculate_match_score
                metadata = enhance_job_with_metadata(job.description or "", job.location or "")
                
                # Update job fields if not already set
                if job.yoe_min is None:
                    job.yoe_min = metadata.get("yoe_min")
                if job.yoe_max is None:
                    job.yoe_max = metadata.get("yoe_max")
                if job.visa_sponsorship is None:
                    job.visa_sponsorship = metadata.get("visa_sponsorship")
                if job.salary_min is None:
                    job.salary_min = metadata.get("salary_min")
                if job.salary_max is None:
                    job.salary_max = metadata.get("salary_max")
                if job.currency is None:
                    job.currency = metadata.get("currency")
                
                # Calculate match_score (default target: 2 YOE)
                if job.match_score is None:
                    job.match_score = calculate_match_score(
                        job.title or "", job.description or "", job.location or "",
                        job.yoe_min, job.yoe_max, target_yoe=2
                    )
            except Exception as e:
                logger.warning(f"Error enhancing job metadata: {e}")
                # Continue without metadata enhancement
            
            jobs.append(job)
    
    logger.info(f"Scraped {len(jobs)} unique jobs from {len(results) - error_count} sources ({error_count} errors). Source breakdown: {source_counts}")
    return jobs
