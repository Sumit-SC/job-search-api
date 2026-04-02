from __future__ import annotations

import argparse
import html
import re
import urllib.parse
from dataclasses import dataclass
from typing import List

import httpx
import feedparser


GOOGLE_SEARCH_URL = "https://www.google.com/search"

# Keep domains broad enough for job discovery.
DEFAULT_JOB_DOMAINS = (
    "linkedin.com",
    "indeed.com",
    "glassdoor.com",
    "naukri.com",
    "foundit.",
    "hirist.com",
    "remotive.com",
    "weworkremotely.com",
    "remoteok.com",
    "workingnomads.com",
    "himalayas.app",
    "jobspresso.co",
    "wellfound.com",
    "workatastartup.com",
    "jobs.lever.co",
    "boards.greenhouse.io",
)


@dataclass
class SearchResult:
    title: str
    url: str
    source: str = "google_basic"


def _strip_tags(s: str) -> str:
    return re.sub(r"<[^>]+>", "", s or "").strip()


def _extract_google_result_links(page_html: str) -> List[str]:
    # Google search links usually look like /url?q=<target>&sa=...
    matches = re.findall(r'href="/url\?q=([^"&]+)[^"]*"', page_html)
    urls: List[str] = []
    seen = set()
    for m in matches:
        try:
            u = urllib.parse.unquote(m)
        except Exception:
            continue
        if not u.startswith("http"):
            continue
        if u in seen:
            continue
        seen.add(u)
        urls.append(u)
    return urls


def _extract_titles(page_html: str) -> List[str]:
    # Very loose extraction; Google markup changes often.
    h3 = re.findall(r"<h3[^>]*>(.*?)</h3>", page_html, flags=re.IGNORECASE | re.DOTALL)
    out: List[str] = []
    for t in h3:
        txt = html.unescape(_strip_tags(t))
        if txt:
            out.append(txt)
    return out


def scrape_google_jobs_basic(query: str, location: str = "remote", limit: int = 20) -> List[SearchResult]:
    q = f"{query} jobs {location}".strip()
    params = {
        "q": q,
        "hl": "en",
        "num": max(10, min(limit * 2, 50)),
        # `udm=8` is often used for jobs-like surface, but can still vary.
        "udm": "8",
    }
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0.0.0 Safari/537.36"
        ),
        "Accept-Language": "en-US,en;q=0.9",
    }

    with httpx.Client(timeout=20, follow_redirects=True, headers=headers) as client:
        res = client.get(GOOGLE_SEARCH_URL, params=params)
        res.raise_for_status()
        page = res.text

    urls = _extract_google_result_links(page)
    titles = _extract_titles(page)

    results: List[SearchResult] = []
    ti = 0
    for u in urls:
        lu = u.lower()
        if not any(d in lu for d in DEFAULT_JOB_DOMAINS):
            continue
        title = titles[ti] if ti < len(titles) else urllib.parse.urlparse(u).netloc
        ti += 1
        results.append(SearchResult(title=title, url=u))
        if len(results) >= limit:
            break
    return results


def scrape_google_news_jobs(query: str, location: str = "remote", limit: int = 20) -> List[SearchResult]:
    # Google-indexed results via News RSS; much more stable than parsing Google Search HTML.
    q = f"({query}) jobs ({location}) site:linkedin.com OR site:indeed.com OR site:glassdoor.com OR site:naukri.com OR site:wellfound.com"
    feed_url = f"https://news.google.com/rss/search?q={urllib.parse.quote_plus(q)}&hl=en-IN&gl=IN&ceid=IN:en"
    feed = feedparser.parse(feed_url)
    out: List[SearchResult] = []
    seen = set()
    for e in feed.entries:
        link = (getattr(e, "link", "") or "").strip()
        title = (getattr(e, "title", "") or "").strip()
        if not link or not title or link in seen:
            continue
        seen.add(link)
        out.append(SearchResult(title=title, url=link, source="google_news_rss"))
        if len(out) >= limit:
            break
    return out


def main() -> None:
    parser = argparse.ArgumentParser(description="Basic Google jobs discovery scraper")
    parser.add_argument("--query", default="data analyst", help="Search query")
    parser.add_argument("--location", default="remote", help="Search location")
    parser.add_argument("--limit", type=int, default=15, help="Max results")
    args = parser.parse_args()

    print(f"Running Google basic scraper: query='{args.query}' location='{args.location}'")
    try:
        rows = scrape_google_jobs_basic(args.query, args.location, args.limit)
    except Exception as e:
        print(f"[ERROR] scrape failed: {e}")
        return

    if not rows:
        print("No parsable links from Google Search HTML, falling back to Google News RSS...")
        try:
            rows = scrape_google_news_jobs(args.query, args.location, args.limit)
        except Exception as e:
            print(f"[ERROR] rss fallback failed: {e}")
            return

    print(f"Found {len(rows)} candidate job links")
    for i, r in enumerate(rows, 1):
        print(f"{i:02d}. {r.title}")
        print(f"    {r.url}")


if __name__ == "__main__":
    main()

