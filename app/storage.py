from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path
from typing import List

from .models import Job


DATA_DIR = Path(os.environ.get("JOBS_SCRAPER_DATA_DIR", "data"))
DATA_FILE = DATA_DIR / "jobs.json"


def load_jobs() -> List[Job]:
    if not DATA_FILE.exists():
        return []
    try:
        raw = DATA_FILE.read_text(encoding="utf-8")
        data = json.loads(raw)
        jobs = [Job(**item) for item in data.get("jobs", [])]
    except Exception:
        jobs = []
    return jobs


def save_jobs(jobs: List[Job]) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    payload = {
        "saved_at": datetime.utcnow().isoformat() + "Z",
        "jobs": [j.model_dump(mode="json") for j in jobs],
    }
    DATA_FILE.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
