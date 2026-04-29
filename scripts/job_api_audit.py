from __future__ import annotations

import asyncio
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.main import app
from app.scraper import scrape_all
from app.storage import load_jobs

OUTPUT_DIR = ROOT / "notebooks" / "output"
OUTPUT_PATH = OUTPUT_DIR / "job_api_audit_results.json"


def serialize_response(resp) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "status_code": resp.status_code,
        "ok": resp.status_code == 200,
        "content_type": resp.headers.get("content-type", ""),
    }
    try:
        data = resp.json()
        payload["json_ok"] = True
        payload["body"] = data
        payload["count"] = data.get("count") if isinstance(data, dict) else None
        payload["error"] = data.get("error") if isinstance(data, dict) else None
    except Exception:
        text = resp.text
        payload["json_ok"] = False
        payload["text_preview"] = text[:500]
    return payload


async def run_scraper_checks() -> list[dict[str, Any]]:
    checks: list[dict[str, Any]] = []
    for sources in (["remoteok"], ["remotive"], ["remoteok", "remotive"]):
        started = datetime.now(timezone.utc)
        label = ",".join(sources)
        try:
            jobs = await asyncio.wait_for(
                scrape_all(
                    days=7,
                    query="data analyst",
                    enable_headless=False,
                    mode="rss",
                    sources=sources,
                ),
                timeout=90,
            )
            checks.append(
                {
                    "sources": sources,
                    "label": label,
                    "ok": True,
                    "count": len(jobs),
                    "sample_titles": [job.title for job in jobs[:5]],
                    "sample_sources": sorted({job.source for job in jobs[:10]}),
                    "started_at": started.isoformat(),
                    "finished_at": datetime.now(timezone.utc).isoformat(),
                }
            )
        except Exception as exc:
            checks.append(
                {
                    "sources": sources,
                    "label": label,
                    "ok": False,
                    "count": 0,
                    "error": str(exc),
                    "started_at": started.isoformat(),
                    "finished_at": datetime.now(timezone.utc).isoformat(),
                }
            )
    return checks


def build_summary(results: dict[str, Any]) -> list[str]:
    notes: list[str] = []
    stored = results["stored_jobs_count"]
    if stored > 0:
        notes.append(f"Stored dataset is available with {stored} jobs, so read/search endpoints are usable.")
    else:
        notes.append("Stored dataset is empty, so /jobs depends on running /refresh first.")

    jobs_ok = results["endpoint_checks"]["jobs"]["body"].get("ok")
    search_ok = results["endpoint_checks"]["jobs_search"]["body"].get("ok")
    if jobs_ok and search_ok:
        notes.append("Core listing endpoints `/jobs` and `/jobs/search` are working.")

    pagination_error = results["endpoint_checks"]["jobs_bad_pagination"]["body"].get("error")
    if pagination_error:
        notes.append(f"Pagination guard is working: {pagination_error}")

    scraper_checks = results["scraper_checks"]
    scraper_success = [check for check in scraper_checks if check.get("ok")]
    if scraper_success:
        notes.append(
            "Live scraping reached at least one source: "
            + ", ".join(f'{c["label"]} ({c["count"]})' for c in scraper_success)
        )
    else:
        notes.append("Live scraping checks did not return results in this run.")
    return notes


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    client = TestClient(app)

    endpoint_checks = {
        "health": serialize_response(client.get("/health")),
        "jobs": serialize_response(client.get("/jobs", params={"q": "data analyst", "days": 7, "limit": 10})),
        "jobs_profiled": serialize_response(
            client.get(
                "/jobs",
                params={
                    "q": "data analyst",
                    "days": 14,
                    "limit": 20,
                    "sort": "relevance",
                    "role_profile": "data_analytics",
                },
            )
        ),
        "jobs_bad_pagination": serialize_response(client.get("/jobs", params={"page": 1})),
        "jobs_search": serialize_response(
            client.get(
                "/jobs/search",
                params={
                    "q": "data analyst",
                    "days": 14,
                    "remote_only": True,
                    "min_match_score": 40,
                    "page": 1,
                    "per_page": 5,
                },
            )
        ),
        "grouped_currency": serialize_response(
            client.get("/jobs/grouped-by-currency", params={"q": "data analyst", "days": 30})
        ),
        "rss": serialize_response(client.get("/jobs/rss", params={"q": "data analyst", "days": 7, "limit": 5})),
    }

    results: dict[str, Any] = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "stored_jobs_count": len(load_jobs()),
        "endpoint_checks": endpoint_checks,
        "scraper_checks": asyncio.run(run_scraper_checks()),
    }
    results["summary"] = build_summary(results)

    OUTPUT_PATH.write_text(json.dumps(results, indent=2), encoding="utf-8")
    print(f"Wrote audit results to {OUTPUT_PATH}")
    print(json.dumps({"summary": results["summary"]}, indent=2))


if __name__ == "__main__":
    main()
