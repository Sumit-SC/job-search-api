"""
Comprehensive dry-run test for ALL job scrapers.
Data-domain focused: analyst, data scientist, product analyst, business analyst.

Sources:
  - 17 RSS feeds (10 remote boards + 1 rssjobs.app analyst mega-feed + 6 Google News RSS)
  - 7 JSON APIs (Remotive, Jobicy, hiring.cafe, Himalayas, WorkingNomads, etc.)
  - 19 ATS boards (Greenhouse per-company public APIs)
  - 4 Major boards (The Muse, Naukri, Foundit/Monster India, Hirist)
  - Note: For direct LinkedIn/Glassdoor/Indeed scraping, use jobspy-testing/
"""
import sys, io, json, time
from dataclasses import dataclass
from typing import Optional

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

import requests
import feedparser

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
TIMEOUT = 20


@dataclass
class FeedResult:
    name: str
    url: str
    type: str  # "rss" | "json_api" | "ats" | "board"
    status: int = 0
    jobs_found: int = 0
    sample_title: str = ""
    sample_company: str = ""
    error: str = ""
    elapsed_ms: int = 0


# ─────────────────────────────────────────────────────────────
#  RSS FEEDS
# ─────────────────────────────────────────────────────────────

RSS_FEEDS = {
    # General remote boards
    "WeWorkRemotely":          "https://weworkremotely.com/remote-jobs.rss",
    "Jobscollider":            "https://jobscollider.com/remote-jobs.rss",
    "Jobscollider (Data)":     "https://jobscollider.com/remote-data-jobs.rss",
    "RemoteOK":                "https://remoteok.com/remote-jobs.rss",
    "Remotive (AI/ML)":        "https://remotive.com/remote-jobs/feed/ai-ml",
    "Remotive (All)":          "https://remotive.com/remote-jobs/feed/",
    "Authentic Jobs":          "https://authenticjobs.com/rss/",
    "HN Jobs (hnrss)":         "https://hnrss.org/jobs",
    "RealWorkFromAnywhere":    "https://www.realworkfromanywhere.com/rss.xml",
    "VirtualVocations":        "https://www.virtualvocations.com/jobs/rss",
    # rssjobs.app — 10k+ analyst jobs (role-tag detection classifies sub-roles)
    "rssjobs (Analyst)":       "https://rssjobs.app/feeds?keywords=analyst&location=remote",
    # Google News RSS — aggregates listing pages from major job boards
    "LinkedIn (via GNews)":    "https://news.google.com/rss/search?q=site:linkedin.com+data+analyst+remote",
    "Glassdoor (via GNews)":   "https://news.google.com/rss/search?q=site:glassdoor.com+data+analyst+remote",
    "Indeed (via GNews)":      "https://news.google.com/rss/search?q=site:indeed.com+data+analyst+remote",
    "GNews Data Analyst":      "https://news.google.com/rss/search?q=%22data+analyst%22+remote+hiring",
    "GNews Data Scientist":    "https://news.google.com/rss/search?q=%22data+scientist%22+remote+hiring",
    "GNews Biz Analyst":       "https://news.google.com/rss/search?q=%22business+analyst%22+remote+hiring",
}


def test_rss_feed(name: str, url: str) -> FeedResult:
    result = FeedResult(name=name, url=url, type="rss")
    start = time.time()
    try:
        resp = requests.get(url, timeout=TIMEOUT, headers={"User-Agent": UA}, allow_redirects=True)
        result.status = resp.status_code
        if resp.status_code != 200:
            result.error = f"HTTP {resp.status_code}"
            result.elapsed_ms = int((time.time() - start) * 1000)
            return result

        feed = feedparser.parse(resp.text)
        entries = feed.entries
        result.jobs_found = len(entries)

        if entries:
            e = entries[0]
            title = getattr(e, "title", "")
            result.sample_title = title[:80]
            if " at " in title:
                result.sample_company = title.rsplit(" at ", 1)[1][:40]

    except Exception as e:
        result.error = str(e)[:100]

    result.elapsed_ms = int((time.time() - start) * 1000)
    return result


# ─────────────────────────────────────────────────────────────
#  JSON APIs (free, public)
# ─────────────────────────────────────────────────────────────

def test_remotive_api() -> FeedResult:
    name = "Remotive API"
    url = "https://remotive.com/api/remote-jobs"
    result = FeedResult(name=name, url=url, type="json_api")
    start = time.time()
    try:
        total = 0
        sample_title = ""
        sample_company = ""
        for cat in ["data", "ai-ml", "all-others"]:
            resp = requests.get(url, params={"category": cat, "limit": 50},
                                headers={"User-Agent": UA}, timeout=TIMEOUT)
            if resp.status_code != 200:
                continue
            result.status = resp.status_code
            data = resp.json()
            jobs = data.get("jobs") or data.get("remote-jobs") or []
            total += len(jobs)
            if jobs and not sample_title:
                sample_title = jobs[0].get("title", "")[:80]
                sample_company = jobs[0].get("company_name", "")[:40]

        result.jobs_found = total
        result.sample_title = sample_title
        result.sample_company = sample_company
    except Exception as e:
        result.error = str(e)[:100]
    result.elapsed_ms = int((time.time() - start) * 1000)
    return result


def test_jobicy_api() -> FeedResult:
    name = "Jobicy API"
    url = "https://jobicy.com/api/v2/remote-jobs"
    result = FeedResult(name=name, url=url, type="json_api")
    start = time.time()
    try:
        resp = requests.get(url, params={"count": 50, "tag": "data analyst"},
                            headers={"User-Agent": UA}, timeout=TIMEOUT)
        result.status = resp.status_code
        if resp.status_code == 200:
            data = resp.json()
            jobs = data.get("jobs") or []
            result.jobs_found = len(jobs)
            if jobs:
                result.sample_title = jobs[0].get("jobTitle", "")[:80]
                result.sample_company = jobs[0].get("companyName", "")[:40]
    except Exception as e:
        result.error = str(e)[:100]
    result.elapsed_ms = int((time.time() - start) * 1000)
    return result


def test_hiring_cafe() -> FeedResult:
    name = "hiring.cafe API"
    url = "https://hiring.cafe/api/search-jobs"
    result = FeedResult(name=name, url=url, type="json_api")
    start = time.time()
    try:
        resp = requests.get(url, params={"searchQuery": "analyst", "workplaceTypes": "Remote"},
                            headers={"User-Agent": UA, "Accept": "application/json",
                                     "Referer": "https://hiring.cafe/"},
                            timeout=TIMEOUT)
        result.status = resp.status_code
        if resp.status_code == 200:
            data = resp.json()
            items = data.get("results") or (data if isinstance(data, list) else [])
            result.jobs_found = len(items)
            if items and isinstance(items[0], dict):
                ji = items[0].get("job_information") or {}
                ec = items[0].get("enriched_company_data") or {}
                result.sample_title = (ji.get("title") or "")[:80]
                result.sample_company = (ec.get("name") or "")[:40]
    except Exception as e:
        result.error = str(e)[:100]
    result.elapsed_ms = int((time.time() - start) * 1000)
    return result


def test_himalayas_api() -> FeedResult:
    name = "Himalayas API"
    url = "https://himalayas.app/jobs/api"
    result = FeedResult(name=name, url=url, type="json_api")
    start = time.time()
    try:
        resp = requests.get(url, params={"q": "analyst", "limit": 50},
                            headers={"User-Agent": UA, "Accept": "application/json"},
                            timeout=TIMEOUT)
        result.status = resp.status_code
        if resp.status_code == 200:
            data = resp.json()
            jobs = data.get("jobs") or data.get("data") or data.get("results") or []
            if isinstance(data, list):
                jobs = data
            result.jobs_found = len(jobs)
            if jobs and isinstance(jobs[0], dict):
                result.sample_title = (jobs[0].get("title") or jobs[0].get("jobTitle", ""))[:80]
                result.sample_company = (jobs[0].get("companyName") or jobs[0].get("company", ""))[:40]
    except Exception as e:
        result.error = str(e)[:100]
    result.elapsed_ms = int((time.time() - start) * 1000)
    return result


def test_workingnomads_api() -> FeedResult:
    name = "WorkingNomads API"
    url = "https://www.workingnomads.com/api/exposed_jobs/"
    result = FeedResult(name=name, url=url, type="json_api")
    start = time.time()
    try:
        resp = requests.get(url, headers={"User-Agent": UA}, timeout=TIMEOUT)
        result.status = resp.status_code
        if resp.status_code == 200:
            data = resp.json()
            items = data if isinstance(data, list) else data.get("jobs") or data.get("results") or []
            result.jobs_found = len(items)
            if items and isinstance(items[0], dict):
                result.sample_title = (items[0].get("title") or "")[:80]
                result.sample_company = (items[0].get("company_name") or "")[:40]
    except Exception as e:
        result.error = str(e)[:100]
    result.elapsed_ms = int((time.time() - start) * 1000)
    return result


def test_jobscollider_api() -> FeedResult:
    name = "Jobscollider API"
    url = "https://jobscollider.com/api/search-jobs"
    result = FeedResult(name=name, url=url, type="json_api")
    start = time.time()
    try:
        resp = requests.get(url, params={"title": "data analyst"},
                            headers={"User-Agent": UA}, timeout=TIMEOUT)
        result.status = resp.status_code
        if resp.status_code == 200:
            data = resp.json()
            items = data if isinstance(data, list) else data.get("jobs") or data.get("data") or data.get("results") or []
            result.jobs_found = len(items)
            if items and isinstance(items[0], dict):
                result.sample_title = (items[0].get("title") or items[0].get("jobTitle", ""))[:80]
                result.sample_company = (items[0].get("company") or items[0].get("companyName", ""))[:40]
    except Exception as e:
        result.error = str(e)[:100]
    result.elapsed_ms = int((time.time() - start) * 1000)
    return result


def test_arbeitnow_api() -> FeedResult:
    name = "Arbeitnow API"
    url = "https://www.arbeitnow.com/api/job-board-api"
    result = FeedResult(name=name, url=url, type="json_api")
    start = time.time()
    try:
        resp = requests.get(url, headers={"User-Agent": UA}, timeout=TIMEOUT)
        result.status = resp.status_code
        if resp.status_code == 200:
            data = resp.json()
            jobs = data.get("data") or data.get("jobs") or []
            remote_jobs = [j for j in jobs if j.get("remote", False)]
            result.jobs_found = len(remote_jobs) if remote_jobs else len(jobs)
            if jobs:
                result.sample_title = jobs[0].get("title", "")[:80]
                result.sample_company = jobs[0].get("company_name", "")[:40]
    except Exception as e:
        result.error = str(e)[:100]
    result.elapsed_ms = int((time.time() - start) * 1000)
    return result


# ─────────────────────────────────────────────────────────────
#  ATS BOARDS (Greenhouse, Lever) — per-company public APIs
# ─────────────────────────────────────────────────────────────

GREENHOUSE_BOARDS = [
    "stripe", "airbnb", "coinbase", "datadog", "hubspot",
    "doordash", "gitlab", "notion", "figma", "twitch",
    "cloudflare", "airtable", "plaid", "canva", "mongodb",
    "discord", "hashicorp", "elastic", "postman",
]


def test_greenhouse_boards() -> FeedResult:
    """Greenhouse Job Board API — aggregate jobs from multiple companies."""
    name = "Greenhouse (multi)"
    result = FeedResult(name=name, url="boards-api.greenhouse.io", type="ats")
    start = time.time()
    total = 0
    sample_title = ""
    sample_company = ""

    for board in GREENHOUSE_BOARDS:
        try:
            url = f"https://boards-api.greenhouse.io/v1/boards/{board}/jobs"
            resp = requests.get(url, headers={"User-Agent": UA}, timeout=10)
            if resp.status_code != 200:
                continue
            result.status = 200
            data = resp.json()
            jobs = data.get("jobs") or []
            total += len(jobs)
            if jobs and not sample_title:
                sample_title = (jobs[0].get("title") or "")[:80]
                sample_company = board.capitalize()
        except Exception:
            continue

    result.jobs_found = total
    result.sample_title = sample_title
    result.sample_company = sample_company
    result.elapsed_ms = int((time.time() - start) * 1000)
    return result


def test_greenhouse_single(board: str) -> tuple[int, str, str]:
    """Test a single Greenhouse board, return (count, title, company)."""
    try:
        url = f"https://boards-api.greenhouse.io/v1/boards/{board}/jobs"
        resp = requests.get(url, headers={"User-Agent": UA}, timeout=10)
        if resp.status_code != 200:
            return (0, "", "")
        data = resp.json()
        jobs = data.get("jobs") or []
        title = (jobs[0].get("title") or "")[:80] if jobs else ""
        return (len(jobs), title, board.capitalize())
    except Exception:
        return (0, "", "")


# ─────────────────────────────────────────────────────────────
#  MAJOR JOB BOARDS (The Muse, Naukri, Foundit/Monster India)
# ─────────────────────────────────────────────────────────────

def test_themuse_api() -> FeedResult:
    """The Muse — free public API, 500 req/hr without key."""
    name = "The Muse"
    url = "https://www.themuse.com/api/public/jobs"
    result = FeedResult(name=name, url=url, type="board")
    start = time.time()
    try:
        resp = requests.get(url, params={"page": 1, "category": "Data Science"},
                            headers={"User-Agent": UA}, timeout=TIMEOUT)
        result.status = resp.status_code
        if resp.status_code == 200:
            data = resp.json()
            jobs = data.get("results") or []
            result.jobs_found = data.get("total", len(jobs))
            if jobs:
                result.sample_title = (jobs[0].get("name") or "")[:80]
                co = jobs[0].get("company") or {}
                result.sample_company = (co.get("name") or "")[:40] if isinstance(co, dict) else str(co)[:40]
    except Exception as e:
        result.error = str(e)[:100]
    result.elapsed_ms = int((time.time() - start) * 1000)
    return result


def test_naukri_api() -> FeedResult:
    """Naukri.com — internal search API (may block non-browser requests)."""
    name = "Naukri (India)"
    url = "https://www.naukri.com/jobapi/v3/search"
    result = FeedResult(name=name, url=url, type="board")
    start = time.time()
    try:
        headers = {
            "User-Agent": UA,
            "Accept": "application/json",
            "appid": "109",
            "systemid": "109",
            "gid": "LOCATION,INDUSTRY,EDUCATION,FAREA_ROLE",
            "Content-Type": "application/json",
        }
        params = {
            "noOfResults": 20,
            "urlType": "search_by_keyword",
            "searchType": "adv",
            "keyword": "data analyst",
            "pageNo": 1,
            "k": "data analyst",
            "stype": "1",
            "src": "jobsearchDesk",
            "latLong": "",
        }
        resp = requests.get(url, params=params, headers=headers, timeout=TIMEOUT)
        result.status = resp.status_code
        if resp.status_code == 200:
            data = resp.json()
            jobs = data.get("jobDetails") or []
            result.jobs_found = data.get("noOfJobs", len(jobs))
            if jobs:
                result.sample_title = (jobs[0].get("title") or "")[:80]
                result.sample_company = (jobs[0].get("companyName") or "")[:40]
        else:
            result.error = f"HTTP {resp.status_code} (needs headless browser)"
    except Exception as e:
        result.error = str(e)[:100]
    result.elapsed_ms = int((time.time() - start) * 1000)
    return result


def test_foundit_api() -> FeedResult:
    """Foundit.in (formerly Monster India) — search API."""
    name = "Foundit/Monster India"
    url = "https://apigw.foundit.in/search/v2/search"
    result = FeedResult(name=name, url=url, type="board")
    start = time.time()
    try:
        headers = {
            "User-Agent": UA,
            "Accept": "application/json",
            "Content-Type": "application/json",
        }
        body = {"query": "data analyst", "limit": 20, "offset": 0, "sort": {"field": "relevance", "order": "desc"}}
        resp = requests.post(url, json=body, headers=headers, timeout=TIMEOUT)
        result.status = resp.status_code
        if resp.status_code == 200:
            data = resp.json()
            jobs = data.get("jobDetails") or data.get("results") or data.get("data") or []
            if isinstance(data, list):
                jobs = data
            result.jobs_found = len(jobs)
            if jobs and isinstance(jobs[0], dict):
                result.sample_title = (jobs[0].get("title") or jobs[0].get("designation", ""))[:80]
                result.sample_company = (jobs[0].get("companyName") or jobs[0].get("company", ""))[:40]
        else:
            result.error = f"HTTP {resp.status_code} (needs headless browser)"
    except Exception as e:
        result.error = str(e)[:100]
    result.elapsed_ms = int((time.time() - start) * 1000)
    return result


def test_hirist_api() -> FeedResult:
    """Hirist.com — Indian tech job portal."""
    name = "Hirist.com (India)"
    url = "https://www.hirist.com/j/data-analyst-jobs.html"
    result = FeedResult(name=name, url=url, type="board")
    start = time.time()
    try:
        resp = requests.get(url, headers={"User-Agent": UA}, timeout=TIMEOUT, allow_redirects=True)
        result.status = resp.status_code
        if resp.status_code == 200:
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(resp.text, "html.parser")
            cards = soup.select(".job-card, .jobCard, [class*='job-list'], .vacancy, .job-bx")
            result.jobs_found = len(cards)
            if cards:
                title_el = cards[0].select_one("h2, h3, .job-title, a[title], .jobTitle")
                if title_el:
                    result.sample_title = title_el.get_text(strip=True)[:80]
            if not result.jobs_found:
                result.error = "Page loaded but no job cards found (needs headless browser)"
        else:
            result.error = f"HTTP {resp.status_code}"
    except ImportError:
        result.error = "beautifulsoup4 not installed"
    except Exception as e:
        result.error = str(e)[:100]
    result.elapsed_ms = int((time.time() - start) * 1000)
    return result


# ─────────────────────────────────────────────────────────────
#  MAIN
# ─────────────────────────────────────────────────────────────

def print_result(r: FeedResult):
    status = "PASS" if r.jobs_found > 0 else ("FAIL" if r.error else "EMPTY")
    icon = "+" if status == "PASS" else ("-" if status == "EMPTY" else "X")
    print(f"  [{icon}] {r.name:<28s} | {r.type:<8s} | {r.status:>3d} | {r.jobs_found:>5d} jobs | {r.elapsed_ms:>5d}ms", end="")
    if r.error:
        print(f" | ERR: {r.error[:60]}", end="")
    print()
    if r.sample_title:
        print(f"       Sample: {r.sample_title}")
        if r.sample_company:
            print(f"       Company: {r.sample_company}")


if __name__ == "__main__":
    print("=" * 70)
    print("COMPREHENSIVE SCRAPER DRY RUN")
    print("Remote + Data/Analyst focused | All sources")
    print("=" * 70)

    results: list[FeedResult] = []

    # ── RSS Feeds ──
    print(f"\n--- RSS Feeds ({len(RSS_FEEDS)} sources) ---\n")
    for name, url in RSS_FEEDS.items():
        r = test_rss_feed(name, url)
        print_result(r)
        results.append(r)

    # ── JSON APIs ──
    api_tests = [
        test_remotive_api,
        test_jobicy_api,
        test_hiring_cafe,
        test_arbeitnow_api,
        test_himalayas_api,
        test_workingnomads_api,
        test_jobscollider_api,
    ]
    print(f"\n--- JSON APIs ({len(api_tests)} sources) ---\n")
    for fn in api_tests:
        r = fn()
        print_result(r)
        results.append(r)

    # ── ATS Boards (Greenhouse) ──
    ats_tests = [
        test_greenhouse_boards,
    ]
    print(f"\n--- ATS Boards ({len(GREENHOUSE_BOARDS)} Greenhouse company boards) ---\n")
    for fn in ats_tests:
        r = fn()
        print_result(r)
        results.append(r)

    # ── Major Job Boards ──
    board_tests = [
        test_themuse_api,
        test_naukri_api,
        test_foundit_api,
        test_hirist_api,
    ]
    print(f"\n--- Major Job Boards ({len(board_tests)} sources) ---\n")
    for fn in board_tests:
        r = fn()
        print_result(r)
        results.append(r)

    # ── Summary ──
    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)

    passed = [r for r in results if r.jobs_found > 0]
    failed = [r for r in results if r.error]
    empty = [r for r in results if r.jobs_found == 0 and not r.error]
    total_jobs = sum(r.jobs_found for r in results)

    print(f"\n  Sources tested: {len(results)}")
    print(f"  Working (PASS): {len(passed)}")
    print(f"  Empty (0 jobs): {len(empty)}")
    print(f"  Errors (FAIL):  {len(failed)}")
    print(f"  Total jobs:     {total_jobs:,}")

    if passed:
        print(f"\n  Top sources by job count:")
        for r in sorted(passed, key=lambda x: x.jobs_found, reverse=True)[:15]:
            print(f"    {r.jobs_found:>6,} | {r.name} ({r.type})")

    if failed:
        print(f"\n  Failed sources:")
        for r in failed:
            print(f"    {r.name}: {r.error[:70]}")

    if empty:
        print(f"\n  Empty sources (may need different query/timing):")
        for r in empty:
            print(f"    {r.name}")

    print(f"\n  NOTE: LinkedIn, Glassdoor, ZipRecruiter need headless browser.")
    print(f"  Use jobspy-testing/ for those (python-jobspy library).")
    print(f"\n{'=' * 70}")
