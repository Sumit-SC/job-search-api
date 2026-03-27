from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple

from pydantic import BaseModel, Field

from .models import Job
from .scoring import calculate_match_score, enhance_job_with_metadata


AGENT_DATA_DIR = Path(os.environ.get("JOBS_AGENT_DATA_DIR", os.environ.get("JOBS_SCRAPER_DATA_DIR", "data")))
PROFILE_FILE = AGENT_DATA_DIR / "agent_profile.json"
LAST_RUN_FILE = AGENT_DATA_DIR / "agent_last_run.json"


class AgentProfile(BaseModel):
    """User requirements for the job-search agent."""

    name: str = Field(default="default", description="Profile name")
    query: str = Field(default="data analyst", description="Search query")
    days: int = Field(default=7, ge=1, le=30, description="Max age of jobs (days)")

    # Hard filters
    include_keywords: List[str] = Field(default_factory=list, description="Must include at least one of these keywords")
    exclude_keywords: List[str] = Field(default_factory=lambda: ["intern", "internship"], description="Exclude if any keyword matches")
    locations_any: List[str] = Field(
        default_factory=lambda: ["remote", "india", "pune", "mumbai", "bangalore", "bengaluru", "hyderabad", "delhi", "ncr", "gurgaon", "noida", "chennai"],
        description="If set, job location text must contain one of these tokens (case-insensitive).",
    )

    yoe_min: Optional[int] = Field(default=2, ge=0, le=40)
    yoe_max: Optional[int] = Field(default=4, ge=0, le=40)

    # Source selection (delegated to scrape_all)
    mode: str = Field(default="rss", description="rss|headless|all")
    enable_headless: bool = Field(default=False, description="Allow Playwright scrapers when available")
    sources: Optional[List[str]] = Field(default=None, description="Optional list of source IDs")

    # Ranking
    target_yoe: int = Field(default=3, ge=0, le=40, description="Target YOE for match_score")
    min_match_score: float = Field(default=55.0, ge=0, le=100, description="Filter out jobs below this match score")


class AgentRunResult(BaseModel):
    ok: bool = True
    profile: AgentProfile
    generated_at: datetime
    count: int
    jobs: List[Job]
    added: List[Job] = Field(default_factory=list)
    removed: List[Job] = Field(default_factory=list)
    error: Optional[str] = None


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _norm_tokens(xs: Iterable[str]) -> List[str]:
    out: List[str] = []
    for x in xs:
        if not x:
            continue
        s = str(x).strip().lower()
        if s:
            out.append(s)
    return out


def load_profile() -> AgentProfile:
    if not PROFILE_FILE.exists():
        return AgentProfile()
    try:
        raw = PROFILE_FILE.read_text(encoding="utf-8")
        data = json.loads(raw)
        return AgentProfile(**data)
    except Exception:
        return AgentProfile()


def save_profile(profile: AgentProfile) -> None:
    AGENT_DATA_DIR.mkdir(parents=True, exist_ok=True)
    PROFILE_FILE.write_text(profile.model_dump_json(indent=2), encoding="utf-8")


def _job_text(job: Job) -> str:
    return f"{job.title} {job.company} {job.location} {job.description} {' '.join(job.tags or [])}".lower()


def _keyword_any_match(text: str, keywords: List[str]) -> bool:
    if not keywords:
        return True
    t = text.lower()
    for kw in keywords:
        if kw and kw.lower() in t:
            return True
    return False


def _keyword_none_match(text: str, keywords: List[str]) -> bool:
    if not keywords:
        return True
    t = text.lower()
    for kw in keywords:
        if kw and kw.lower() in t:
            return False
    return True


def _location_match(loc_text: str, tokens: List[str]) -> bool:
    if not tokens:
        return True
    t = (loc_text or "").lower()
    return any(tok in t for tok in tokens if tok)


def _yoe_ok(job: Job, yoe_min: Optional[int], yoe_max: Optional[int]) -> bool:
    # If job has no YOE, do not reject (keep it, agent can decide).
    if job.yoe_min is None and job.yoe_max is None:
        return True
    # Conservative window check
    if yoe_max is not None and job.yoe_min is not None and job.yoe_min > yoe_max:
        return False
    if yoe_min is not None and job.yoe_max is not None and job.yoe_max < yoe_min:
        return False
    return True


def enrich_and_score(job: Job, profile: AgentProfile) -> Job:
    meta = enhance_job_with_metadata(job.description or "", job.location or "")
    # Only fill if missing
    if job.yoe_min is None:
        job.yoe_min = meta.get("yoe_min")
    if job.yoe_max is None:
        job.yoe_max = meta.get("yoe_max")
    if job.visa_sponsorship is None:
        job.visa_sponsorship = meta.get("visa_sponsorship")
    if job.salary_min is None:
        job.salary_min = meta.get("salary_min")
    if job.salary_max is None:
        job.salary_max = meta.get("salary_max")
    if job.currency is None:
        job.currency = meta.get("currency")

    job.match_score = calculate_match_score(
        job_title=job.title or "",
        job_description=job.description or "",
        job_location=job.location or "",
        job_yoe_min=job.yoe_min,
        job_yoe_max=job.yoe_max,
        target_yoe=profile.target_yoe,
    )
    # Keep `rank` aligned with match_score for now
    job.rank = float(job.match_score or 0.0)
    return job


def filter_jobs(jobs: List[Job], profile: AgentProfile) -> List[Job]:
    include = _norm_tokens(profile.include_keywords)
    exclude = _norm_tokens(profile.exclude_keywords)
    loc_tokens = _norm_tokens(profile.locations_any)
    out: List[Job] = []
    for j in jobs:
        text = _job_text(j)
        if not _keyword_any_match(text, include):
            continue
        if not _keyword_none_match(text, exclude):
            continue
        if not _location_match(j.location or "", loc_tokens):
            continue
        if not _yoe_ok(j, profile.yoe_min, profile.yoe_max):
            continue
        if (j.match_score is not None) and float(j.match_score) < float(profile.min_match_score):
            continue
        out.append(j)
    return out


def _job_key(job: Job) -> str:
    # URL is the best global stable identifier across sources.
    return str(job.url)


def diff_jobs(prev: List[Job], curr: List[Job]) -> Tuple[List[Job], List[Job]]:
    prev_map: Dict[str, Job] = { _job_key(j): j for j in prev if j and j.url }
    curr_map: Dict[str, Job] = { _job_key(j): j for j in curr if j and j.url }
    added = [curr_map[k] for k in curr_map.keys() if k not in prev_map]
    removed = [prev_map[k] for k in prev_map.keys() if k not in curr_map]
    return added, removed


def load_last_run_jobs() -> List[Job]:
    if not LAST_RUN_FILE.exists():
        return []
    try:
        raw = LAST_RUN_FILE.read_text(encoding="utf-8")
        data = json.loads(raw)
        jobs = []
        for item in data.get("jobs", []):
            try:
                jobs.append(Job(**item))
            except Exception:
                continue
        return jobs
    except Exception:
        return []


def save_last_run(profile: AgentProfile, jobs: List[Job]) -> None:
    AGENT_DATA_DIR.mkdir(parents=True, exist_ok=True)
    payload = {
        "saved_at": _now_utc().isoformat(),
        "profile": profile.model_dump(),
        "jobs": [j.model_dump(mode="json") for j in jobs],
    }
    LAST_RUN_FILE.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

