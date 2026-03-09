"""
Local server for custom scrapers testing.
Serves the UI and proxies all job source APIs (avoids CORS issues).

Data-domain focused: analyst, data scientist, product analyst, business analyst.
Auto-tags jobs by role type with proper timestamps.

Usage:
    .venv\\Scripts\\python server.py
    Then open http://localhost:8899
"""
import sys, io, json, time, os, re
from http.server import HTTPServer, SimpleHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
from datetime import datetime
import requests
import feedparser

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

PORT = int(os.environ.get("PORT", 8899))
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
TIMEOUT = 20

# ── Role-tag detection ────────────────────────────────────────

ROLE_PATTERNS = [
    ("Data Analyst",       re.compile(r"\bdata\s*analyst\b", re.I)),
    ("Business Analyst",   re.compile(r"\bbusiness\s*analyst\b", re.I)),
    ("Product Analyst",    re.compile(r"\bproduct\s*analyst\b", re.I)),
    ("Data Scientist",     re.compile(r"\bdata\s*scien", re.I)),
    ("Data Engineer",      re.compile(r"\bdata\s*engineer", re.I)),
    ("ML Engineer",        re.compile(r"\b(ml|machine\s*learn)\s*engineer", re.I)),
    ("Analytics Engineer", re.compile(r"\banalytics\s*engineer", re.I)),
    ("BI Analyst",         re.compile(r"\b(bi|business\s*intelligence)\s*(analyst|engineer|developer)", re.I)),
    ("Quantitative",       re.compile(r"\bquant(itative)?\s*(analyst|researcher|developer)", re.I)),
    ("Research Analyst",   re.compile(r"\bresearch\s*analyst\b", re.I)),
    ("Financial Analyst",  re.compile(r"\bfinancial?\s*analyst\b", re.I)),
    ("Operations Analyst", re.compile(r"\boperations?\s*analyst\b", re.I)),
    ("Marketing Analyst",  re.compile(r"\bmarketing\s*analyst\b", re.I)),
    ("AI/ML",              re.compile(r"\b(artificial\s*intelligence|ai\/ml|deep\s*learn|llm|nlp)\b", re.I)),
    ("Analyst",            re.compile(r"\banalyst\b", re.I)),
]

SENIORITY_PATTERNS = [
    ("Intern",    re.compile(r"\b(intern|internship|trainee)\b", re.I)),
    ("Junior",    re.compile(r"\b(junior|jr\.?|entry[\s-]level|associate(?!\s+director))\b", re.I)),
    ("Mid",       re.compile(r"\b(mid[\s-]?level)\b", re.I)),
    ("Senior",    re.compile(r"\b(senior|sr\.?)\b", re.I)),
    ("Staff",     re.compile(r"\b(staff|principal)\b", re.I)),
    ("Lead",      re.compile(r"\b(lead|team\s*lead)\b", re.I)),
    ("Manager",   re.compile(r"\b(manager|head\s*of|director)\b", re.I)),
]


def detect_role_tags(title: str) -> list[str]:
    tags = []
    for label, pat in ROLE_PATTERNS:
        if pat.search(title):
            tags.append(label)
    return tags[:3] if tags else []


def detect_seniority(title: str) -> str:
    for label, pat in SENIORITY_PATTERNS:
        if pat.search(title):
            return label
    return ""


def parse_timestamp(raw: str) -> str:
    """Normalize any date string to ISO 8601."""
    if not raw:
        return ""
    try:
        for fmt in [
            "%Y-%m-%dT%H:%M:%S",
            "%Y-%m-%dT%H:%M:%SZ",
            "%Y-%m-%dT%H:%M:%S%z",
            "%a, %d %b %Y %H:%M:%S %z",
            "%a, %d %b %Y %H:%M:%S GMT",
            "%Y-%m-%d %H:%M:%S",
            "%Y-%m-%d",
        ]:
            try:
                dt = datetime.strptime(raw.strip()[:30], fmt)
                return dt.isoformat()
            except ValueError:
                continue
        from email.utils import parsedate_to_datetime
        dt = parsedate_to_datetime(raw)
        return dt.isoformat()
    except Exception:
        return raw


def enrich_job(job: dict) -> dict:
    """Add role tags, seniority, and normalized timestamp."""
    title = job.get("title", "")
    job["role_tags"] = detect_role_tags(title)
    if not job.get("seniority"):
        job["seniority"] = detect_seniority(title)
    job["date_iso"] = parse_timestamp(job.get("date", ""))
    return job


# ── Source definitions ───────────────────────────────────────

RSS_FEEDS = {
    # General remote boards
    "weworkremotely":          {"name": "WeWorkRemotely",          "url": "https://weworkremotely.com/remote-jobs.rss",                                            "category": "remote"},
    "jobscollider":            {"name": "Jobscollider",            "url": "https://jobscollider.com/remote-jobs.rss",                                              "category": "remote"},
    "jobscollider_data":       {"name": "Jobscollider (Data)",     "url": "https://jobscollider.com/remote-data-jobs.rss",                                         "category": "data"},
    "remoteok":                {"name": "RemoteOK",                "url": "https://remoteok.com/remote-jobs.rss",                                                  "category": "remote"},
    "remotive_aiml":           {"name": "Remotive (AI/ML)",        "url": "https://remotive.com/remote-jobs/feed/ai-ml",                                           "category": "data"},
    "remotive_all":            {"name": "Remotive (All)",          "url": "https://remotive.com/remote-jobs/feed/",                                                "category": "remote"},
    "authentic_jobs":          {"name": "Authentic Jobs",          "url": "https://authenticjobs.com/rss/",                                                        "category": "remote"},
    "hn_jobs":                 {"name": "HN Jobs",                 "url": "https://hnrss.org/jobs",                                                                "category": "tech"},
    "realworkfromanywhere":    {"name": "RealWorkFromAnywhere",    "url": "https://www.realworkfromanywhere.com/rss.xml",                                           "category": "remote"},
    "virtualvocations":        {"name": "VirtualVocations",        "url": "https://www.virtualvocations.com/jobs/rss",                                             "category": "remote"},
    # rssjobs.app — 10k+ analyst jobs (only "analyst" keyword works, role-tag detection classifies them)
    "rssjobs_analyst":         {"name": "rssjobs (Analyst)",       "url": "https://rssjobs.app/feeds?keywords=analyst&location=remote",                             "category": "data"},
    # Google News RSS — aggregates job listing pages from major boards
    "gnews_linkedin":          {"name": "LinkedIn (via GNews)",    "url": "https://news.google.com/rss/search?q=site:linkedin.com+data+analyst+remote",             "category": "data"},
    "gnews_glassdoor":         {"name": "Glassdoor (via GNews)",   "url": "https://news.google.com/rss/search?q=site:glassdoor.com+data+analyst+remote",            "category": "data"},
    "gnews_indeed":            {"name": "Indeed (via GNews)",      "url": "https://news.google.com/rss/search?q=site:indeed.com+data+analyst+remote",               "category": "data"},
    "gnews_analyst_remote":    {"name": "GNews Data Analyst",      "url": "https://news.google.com/rss/search?q=%22data+analyst%22+remote+hiring",                  "category": "data"},
    "gnews_ds_remote":         {"name": "GNews Data Scientist",    "url": "https://news.google.com/rss/search?q=%22data+scientist%22+remote+hiring",                "category": "data"},
    "gnews_ba_remote":         {"name": "GNews Biz Analyst",       "url": "https://news.google.com/rss/search?q=%22business+analyst%22+remote+hiring",              "category": "data"},
}

JSON_APIS = {
    "jobicy":           {"name": "Jobicy API",        "url": "https://jobicy.com/api/v2/remote-jobs",              "category": "remote"},
    "hiring_cafe":      {"name": "hiring.cafe",       "url": "https://hiring.cafe/api/search-jobs",                "category": "remote"},
    "arbeitnow":        {"name": "Arbeitnow",         "url": "https://www.arbeitnow.com/api/job-board-api",        "category": "remote"},
    "himalayas":        {"name": "Himalayas API",      "url": "https://himalayas.app/jobs/api",                     "category": "remote"},
    "workingnomads":    {"name": "WorkingNomads",      "url": "https://www.workingnomads.com/api/exposed_jobs/",    "category": "remote"},
    "jobscollider_api": {"name": "Jobscollider API",   "url": "https://jobscollider.com/api/search-jobs",          "category": "remote"},
    "remotive_api":     {"name": "Remotive API",       "url": "https://remotive.com/api/remote-jobs",              "category": "data"},
    "themuse":          {"name": "The Muse",           "url": "https://www.themuse.com/api/public/jobs",            "category": "board"},
}

GREENHOUSE_BOARDS = [
    "stripe", "airbnb", "coinbase", "datadog", "hubspot",
    "doordash", "gitlab", "notion", "figma", "twitch",
    "cloudflare", "airtable", "plaid", "canva", "mongodb",
    "discord", "hashicorp", "elastic", "postman",
]


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
            jobs.append(enrich_job({
                "title": title,
                "company": company,
                "url": link,
                "date": getattr(entry, "published", ""),
                "location": "Remote",
                "source": cfg["name"],
                "source_id": source_id,
            }))
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
    elif source_id == "themuse":
        params = {"page": 1, "category": "Data Science"}

    try:
        resp = requests.get(cfg["url"], params=params, headers=headers, timeout=TIMEOUT)
        if resp.status_code != 200:
            return []
        data = resp.json()
    except Exception:
        return []

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
        elif source_id == "themuse":
            co = item.get("company") or {}
            locs = item.get("locations") or []
            loc_str = locs[0].get("name", "") if locs and isinstance(locs[0], dict) else ""
            jobs.append({
                "title": item.get("name", ""),
                "company": co.get("name", "") if isinstance(co, dict) else str(co),
                "url": item.get("refs", {}).get("landing_page", ""),
                "date": item.get("publication_date", ""),
                "location": loc_str,
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
    return [enrich_job(j) for j in jobs]


def fetch_greenhouse(board: str, query: str = "", limit: int = 100) -> list[dict]:
    """Fetch jobs from a single Greenhouse board."""
    try:
        url = f"https://boards-api.greenhouse.io/v1/boards/{board}/jobs"
        resp = requests.get(url, headers={"User-Agent": UA}, timeout=10)
        if resp.status_code != 200:
            return []
        data = resp.json()
        raw_jobs = data.get("jobs") or []
        jobs = []
        for item in raw_jobs[:limit]:
            title = item.get("title", "")
            if query and query.lower() not in title.lower():
                continue
            loc = item.get("location") or {}
            jobs.append(enrich_job({
                "title": title,
                "company": board.capitalize(),
                "url": item.get("absolute_url", ""),
                "date": item.get("updated_at", ""),
                "location": loc.get("name", "") if isinstance(loc, dict) else str(loc),
                "source": f"Greenhouse ({board})",
                "source_id": f"greenhouse_{board}",
            }))
        return jobs
    except Exception:
        return []


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
            for board in GREENHOUSE_BOARDS:
                sources[f"greenhouse_{board}"] = {"name": f"Greenhouse ({board.capitalize()})", "type": "ats", "category": "ats"}
            self._json_response(sources)
            return

        if path == "/api/fetch":
            qs = parse_qs(parsed.query)
            source_ids = qs.get("sources", ["all"])[0].split(",")
            query = qs.get("q", ["analyst"])[0]
            limit = int(qs.get("limit", ["100"])[0])

            if "all" in source_ids:
                source_ids = (
                    list(RSS_FEEDS.keys()) +
                    list(JSON_APIS.keys()) +
                    [f"greenhouse_{b}" for b in GREENHOUSE_BOARDS]
                )

            all_jobs = []
            source_stats = {}
            for sid in source_ids:
                start = time.time()
                jobs = []
                if sid in RSS_FEEDS:
                    jobs = fetch_rss(sid, query, limit)
                elif sid in JSON_APIS:
                    jobs = fetch_json_api(sid, query, limit)
                elif sid.startswith("greenhouse_"):
                    board = sid.replace("greenhouse_", "")
                    if board in GREENHOUSE_BOARDS:
                        jobs = fetch_greenhouse(board, query, limit)
                else:
                    continue
                elapsed = int((time.time() - start) * 1000)
                name = sid
                if sid in RSS_FEEDS:
                    name = RSS_FEEDS[sid]["name"]
                elif sid in JSON_APIS:
                    name = JSON_APIS[sid]["name"]
                elif sid.startswith("greenhouse_"):
                    name = f"Greenhouse ({sid.replace('greenhouse_', '').capitalize()})"
                source_stats[sid] = {"count": len(jobs), "ms": elapsed, "name": name}
                all_jobs.extend(jobs)

            # Deduplicate by (title_lower, company_lower)
            seen = set()
            unique_jobs = []
            for j in all_jobs:
                key = (j.get("title", "").lower().strip(), j.get("company", "").lower().strip())
                if key not in seen:
                    seen.add(key)
                    unique_jobs.append(j)

            # Collect all role tags found
            all_role_tags = sorted(set(
                tag for j in unique_jobs for tag in j.get("role_tags", [])
            ))

            self._json_response({
                "ok": True,
                "total": len(unique_jobs),
                "duplicates_removed": len(all_jobs) - len(unique_jobs),
                "role_tags_found": all_role_tags,
                "sources": source_stats,
                "jobs": unique_jobs,
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
    total = len(RSS_FEEDS) + len(JSON_APIS) + len(GREENHOUSE_BOARDS)
    server = HTTPServer(("127.0.0.1", PORT), Handler)
    print(f"Custom Scrapers UI running at http://localhost:{PORT}")
    print(f"Sources: {len(RSS_FEEDS)} RSS + {len(JSON_APIS)} JSON APIs + {len(GREENHOUSE_BOARDS)} Greenhouse boards = {total} total")
    print("Press Ctrl+C to stop.\n")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")
