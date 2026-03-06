"""
Local server for custom scrapers testing.
Serves the UI and proxies all job source APIs (avoids CORS issues).

Usage:
    .venv\Scripts\python server.py
    Then open http://localhost:8899
"""
import sys, io, json, time, os
from http.server import HTTPServer, SimpleHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
import requests
import feedparser

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

PORT = int(os.environ.get("PORT", 8899))
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
TIMEOUT = 20

# ── Source definitions ───────────────────────────────────────

RSS_FEEDS = {
    "weworkremotely":       {"name": "WeWorkRemotely",      "url": "https://weworkremotely.com/remote-jobs.rss",                "category": "remote"},
    "jobscollider":         {"name": "Jobscollider",        "url": "https://jobscollider.com/remote-jobs.rss",                  "category": "remote"},
    "jobscollider_data":    {"name": "Jobscollider (Data)", "url": "https://jobscollider.com/remote-data-jobs.rss",             "category": "data"},
    "remoteok":             {"name": "RemoteOK",            "url": "https://remoteok.com/remote-jobs.rss",                      "category": "remote"},
    "remotive_data":        {"name": "Remotive (Data)",     "url": "https://remotive.com/remote-jobs/feed/data",                "category": "data"},
    "remotive_aiml":        {"name": "Remotive (AI/ML)",    "url": "https://remotive.com/remote-jobs/feed/ai-ml",               "category": "data"},
    "jobspresso":           {"name": "Jobspresso",          "url": "https://jobspresso.co/remote-jobs/feed/",                   "category": "remote"},
    "authentic_jobs":       {"name": "Authentic Jobs",      "url": "https://authenticjobs.com/rss/",                            "category": "remote"},
    "hn_jobs":              {"name": "HN Jobs",             "url": "https://hnrss.org/jobs",                                    "category": "tech"},
    "rssjobs":              {"name": "rssjobs.app",         "url": "https://rssjobs.app/feeds?keywords={q}&location=remote",    "category": "remote"},
    "realworkfromanywhere": {"name": "RealWorkFromAnywhere","url": "https://www.realworkfromanywhere.com/rss.xml",              "category": "remote"},
    "jobicy_rss":           {"name": "Jobicy RSS",          "url": "https://jobicy.com/jobs-rss-feed",                          "category": "remote"},
}

JSON_APIS = {
    "jobicy":           {"name": "Jobicy API",        "url": "https://jobicy.com/api/v2/remote-jobs",              "category": "remote"},
    "hiring_cafe":      {"name": "hiring.cafe",       "url": "https://hiring.cafe/api/search-jobs",                "category": "remote"},
    "arbeitnow":        {"name": "Arbeitnow",         "url": "https://www.arbeitnow.com/api/job-board-api",        "category": "remote"},
    "himalayas":        {"name": "Himalayas API",      "url": "https://himalayas.app/jobs/api",                     "category": "remote"},
    "workingnomads":    {"name": "WorkingNomads",      "url": "https://www.workingnomads.com/api/exposed_jobs/",    "category": "remote"},
    "jobscollider_api": {"name": "Jobscollider API",   "url": "https://jobscollider.com/api/search-jobs",          "category": "remote"},
    "remotive_api":     {"name": "Remotive API",       "url": "https://remotive.com/api/remote-jobs",              "category": "data"},
}


def fetch_rss(source_id: str, query: str = "analyst", limit: int = 100) -> list[dict]:
    cfg = RSS_FEEDS.get(source_id)
    if not cfg:
        return []
    url = cfg["url"].replace("{q}", query.replace(" ", "+"))
    try:
        resp = requests.get(url, timeout=TIMEOUT, headers={"User-Agent": UA})
        if resp.status_code != 200:
            return []
        feed = feedparser.parse(resp.text)
        jobs = []
        for entry in feed.entries[:limit]:
            title = getattr(entry, "title", "")
            company = ""
            if " at " in title:
                parts = title.rsplit(" at ", 1)
                title = parts[0].strip()
                company = parts[1].strip()
            link = getattr(entry, "link", "")
            jobs.append({
                "title": title,
                "company": company,
                "url": link,
                "date": getattr(entry, "published", ""),
                "location": "Remote",
                "source": cfg["name"],
                "source_id": source_id,
            })
        return jobs
    except Exception:
        return []


def fetch_json_api(source_id: str, query: str = "analyst", limit: int = 100) -> list[dict]:
    cfg = JSON_APIS.get(source_id)
    if not cfg:
        return []
    headers = {"User-Agent": UA, "Accept": "application/json"}
    params = {}

    if source_id == "jobicy":
        params = {"count": min(limit, 50), "tag": query}
    elif source_id == "hiring_cafe":
        params = {"searchQuery": query, "workplaceTypes": "Remote"}
        headers["Referer"] = "https://hiring.cafe/"
    elif source_id == "himalayas":
        params = {"q": query, "limit": min(limit, 50)}
    elif source_id == "workingnomads":
        pass
    elif source_id == "jobscollider_api":
        params = {"title": query}
    elif source_id == "remotive_api":
        params = {"category": "data", "search": query, "limit": min(limit, 50)}

    try:
        resp = requests.get(cfg["url"], params=params, headers=headers, timeout=TIMEOUT)
        if resp.status_code != 200:
            return []
        data = resp.json()
    except Exception:
        return []

    # Normalize response to list of items
    items = []
    if isinstance(data, list):
        items = data
    elif isinstance(data, dict):
        for key in ["results", "jobs", "data", "remote-jobs"]:
            if key in data and isinstance(data[key], list):
                items = data[key]
                break

    jobs = []
    for item in items[:limit]:
        if not isinstance(item, dict):
            continue

        if source_id == "hiring_cafe":
            ji = item.get("job_information") or {}
            vpd = item.get("v5_processed_job_data") or {}
            ec = item.get("enriched_company_data") or {}
            comp = ""
            cur = vpd.get("listed_compensation_currency") or "USD"
            for p in ["yearly", "monthly", "hourly"]:
                lo = vpd.get(f"{p}_min_compensation")
                hi = vpd.get(f"{p}_max_compensation")
                if lo or hi:
                    lo_s = f"{lo:,.0f}" if isinstance(lo, (int, float)) else str(lo or "?")
                    hi_s = f"{hi:,.0f}" if isinstance(hi, (int, float)) else str(hi or "?")
                    comp = f"{cur} {lo_s}-{hi_s} {p}"
                    break
            jobs.append({
                "title": ji.get("title") or vpd.get("core_job_title", ""),
                "company": ec.get("name") or vpd.get("company_name", ""),
                "url": item.get("apply_url", ""),
                "date": vpd.get("estimated_publish_date", ""),
                "location": vpd.get("formatted_workplace_location", ""),
                "workplace": vpd.get("workplace_type", ""),
                "seniority": vpd.get("seniority_level", ""),
                "commitment": ", ".join(vpd.get("commitment") or []),
                "compensation": comp,
                "skills": ", ".join((vpd.get("technical_tools") or [])[:5]),
                "source": cfg["name"],
                "source_id": source_id,
                "expired": item.get("is_expired", False),
            })
        elif source_id == "jobicy":
            jobs.append({
                "title": item.get("jobTitle", ""),
                "company": item.get("companyName", ""),
                "url": item.get("url", ""),
                "date": item.get("pubDate", ""),
                "location": item.get("jobGeo", "Remote"),
                "compensation": item.get("annualSalaryMin", ""),
                "source": cfg["name"],
                "source_id": source_id,
            })
        elif source_id == "workingnomads":
            jobs.append({
                "title": item.get("title", ""),
                "company": item.get("company_name", ""),
                "url": item.get("url", ""),
                "date": item.get("pub_date", ""),
                "location": item.get("location", "Remote"),
                "category": item.get("category_name", ""),
                "source": cfg["name"],
                "source_id": source_id,
            })
        else:
            jobs.append({
                "title": item.get("title") or item.get("jobTitle", ""),
                "company": item.get("company_name") or item.get("companyName") or item.get("company", ""),
                "url": item.get("url") or item.get("link", ""),
                "date": item.get("pubDate") or item.get("publication_date") or item.get("created_at", ""),
                "location": item.get("candidate_required_location") or item.get("location") or item.get("jobGeo", ""),
                "source": cfg["name"],
                "source_id": source_id,
            })
    return jobs


class Handler(SimpleHTTPRequestHandler):
    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path

        if path == "/" or path == "/index.html":
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            html_path = os.path.join(os.path.dirname(__file__), "index.html")
            with open(html_path, "rb") as f:
                self.wfile.write(f.read())
            return

        if path == "/api/sources":
            sources = {}
            for sid, cfg in RSS_FEEDS.items():
                sources[sid] = {"name": cfg["name"], "type": "rss", "category": cfg["category"]}
            for sid, cfg in JSON_APIS.items():
                sources[sid] = {"name": cfg["name"], "type": "json_api", "category": cfg["category"]}
            self._json_response(sources)
            return

        if path == "/api/fetch":
            qs = parse_qs(parsed.query)
            source_ids = qs.get("sources", ["all"])[0].split(",")
            query = qs.get("q", ["analyst"])[0]
            limit = int(qs.get("limit", ["100"])[0])

            if "all" in source_ids:
                source_ids = list(RSS_FEEDS.keys()) + list(JSON_APIS.keys())

            all_jobs = []
            source_stats = {}
            for sid in source_ids:
                start = time.time()
                if sid in RSS_FEEDS:
                    jobs = fetch_rss(sid, query, limit)
                elif sid in JSON_APIS:
                    jobs = fetch_json_api(sid, query, limit)
                else:
                    continue
                elapsed = int((time.time() - start) * 1000)
                source_stats[sid] = {"count": len(jobs), "ms": elapsed, "name": (RSS_FEEDS.get(sid) or JSON_APIS.get(sid, {})).get("name", sid)}
                all_jobs.extend(jobs)

            self._json_response({
                "ok": True,
                "total": len(all_jobs),
                "sources": source_stats,
                "jobs": all_jobs,
            })
            return

        self.send_error(404)

    def _json_response(self, data):
        body = json.dumps(data, default=str, ensure_ascii=False).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format, *args):
        print(f"  {args[0]}")


if __name__ == "__main__":
    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    server = HTTPServer(("127.0.0.1", PORT), Handler)
    print(f"Custom Scrapers UI running at http://localhost:{PORT}")
    print(f"Sources: {len(RSS_FEEDS)} RSS + {len(JSON_APIS)} JSON APIs = {len(RSS_FEEDS) + len(JSON_APIS)} total")
    print("Press Ctrl+C to stop.\n")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")
