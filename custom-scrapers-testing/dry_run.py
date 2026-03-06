"""
Comprehensive dry-run test for ALL remote/data-analyst job scrapers.

Sources pulled from existing app/scraper.py + new additions:
  - 14 RSS feeds (remote-focused, data/analyst filtered)
  -  4 JSON APIs (Remotive, Jobicy, hiring.cafe, rssjobs.app)
"""
import sys, io, json, time
from dataclasses import dataclass, field, asdict
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
    type: str  # "rss" | "json_api"
    status: int = 0
    jobs_found: int = 0
    sample_title: str = ""
    sample_company: str = ""
    error: str = ""
    elapsed_ms: int = 0


# ─────────────────────────────────────────────────────────────
#  RSS FEEDS — all from existing scraper.py + new ones
# ─────────────────────────────────────────────────────────────

RSS_FEEDS = {
    # ── Reliable sources from scraper.py ──
    "WeWorkRemotely":       "https://weworkremotely.com/remote-jobs.rss",
    "Jobscollider":         "https://jobscollider.com/remote-jobs.rss",
    "Jobscollider (Data)":  "https://jobscollider.com/remote-data-jobs.rss",
    "RemoteOK":             "https://remoteok.com/remote-jobs.rss",
    "Remotive (Data)":      "https://remotive.com/remote-jobs/feed/data",
    "Remotive (AI/ML)":     "https://remotive.com/remote-jobs/feed/ai-ml",
    "Jobspresso":           "https://jobspresso.co/remote-jobs/feed/",
    "Authentic Jobs":       "https://authenticjobs.com/rss/",
    "HN Jobs (hnrss)":     "https://hnrss.org/jobs",

    # ── New: rssjobs.app (RSS 2.0 XML — massive feed) ──
    "rssjobs.app (analyst)": "https://rssjobs.app/feeds?keywords=analyst&location=remote",

    # ── New RSS sources ──
    "Jobicy RSS":           "https://jobicy.com/jobs-rss-feed",
    "RealWorkFromAnywhere": "https://www.realworkfromanywhere.com/rss.xml",

    # ── Flaky (403/timeout) but worth testing ──
    "Himalayas RSS":        "https://himalayas.app/jobs/feed",
    "Remote.co":            "https://remote.co/remote-jobs/feed/",
    "Wellfound (analyst)":  "https://wellfound.com/jobs.rss?keywords=data-analyst&remote=true",
}


def test_rss_feed(name: str, url: str) -> FeedResult:
    result = FeedResult(name=name, url=url, type="rss")
    start = time.time()
    try:
        resp = requests.get(url, timeout=TIMEOUT, headers={"User-Agent": UA})
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
#  JSON APIs
# ─────────────────────────────────────────────────────────────

def test_remotive_api() -> FeedResult:
    """Remotive public API — data + AI/ML categories."""
    name = "Remotive API (data)"
    url = "https://remotive.com/api/remote-jobs"
    result = FeedResult(name=name, url=url, type="json_api")
    start = time.time()
    try:
        total = 0
        sample_title = ""
        sample_company = ""
        for cat in ["data", "ai-ml"]:
            resp = requests.get(url, params={"category": cat, "search": "analyst", "limit": 50},
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
    """Jobicy public API — remote jobs."""
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
    """hiring.cafe — GET /api/search-jobs."""
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
            items = data.get("results") or data if isinstance(data, list) else data.get("results", [])
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
    """Himalayas.app — JSON API for remote jobs."""
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
    """WorkingNomads — public JSON API for remote jobs."""
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
    """Jobscollider — free remote jobs API."""
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
    """Arbeitnow — free remote jobs API."""
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
#  MAIN
# ─────────────────────────────────────────────────────────────

def print_result(r: FeedResult):
    status = "PASS" if r.jobs_found > 0 else ("FAIL" if r.error else "EMPTY")
    icon = "+" if status == "PASS" else ("-" if status == "EMPTY" else "X")
    print(f"  [{icon}] {r.name:<28s} | {r.type:<8s} | {r.status:>3d} | {r.jobs_found:>5d} jobs | {r.elapsed_ms:>5d}ms", end="")
    if r.error:
        print(f" | ERR: {r.error[:50]}", end="")
    print()
    if r.sample_title:
        print(f"       Sample: {r.sample_title}")
        if r.sample_company:
            print(f"       Company: {r.sample_company}")


if __name__ == "__main__":
    print("=" * 70)
    print("COMPREHENSIVE SCRAPER DRY RUN")
    print("Remote + Data/Analyst focused | All sources from scraper.py + new")
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
        for r in sorted(passed, key=lambda x: x.jobs_found, reverse=True)[:10]:
            print(f"    {r.jobs_found:>6,} | {r.name} ({r.type})")

    if failed:
        print(f"\n  Failed sources:")
        for r in failed:
            print(f"    {r.name}: {r.error[:60]}")

    if empty:
        print(f"\n  Empty sources (may need different query/timing):")
        for r in empty:
            print(f"    {r.name}")

    print(f"\n{'=' * 70}")
