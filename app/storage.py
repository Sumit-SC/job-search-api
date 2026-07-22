from __future__ import annotations

import os
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional

from .models import Job

# Unify data directory and SQLite DB file
DATA_DIR = Path(os.environ.get("JOBS_SCRAPER_DATA_DIR", "data"))
DB_FILE = DATA_DIR / "jobs.db"


def init_db() -> None:
    """Initialize the consolidated SQLite database and build necessary indexes."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_FILE)
    try:
        # 1. Job listings table
        conn.execute("""
            CREATE TABLE IF NOT EXISTS jobs (
                id TEXT PRIMARY KEY,
                title TEXT,
                company TEXT,
                location TEXT,
                url TEXT UNIQUE,
                description TEXT,
                source TEXT,
                date TEXT,
                tags TEXT, -- JSON list serialized
                match_score REAL,
                yoe_min INTEGER,
                yoe_max INTEGER,
                salary_min REAL,
                salary_max REAL,
                currency TEXT,
                visa_sponsorship INTEGER, -- 0=False, 1=True, null=None
                job_type TEXT,
                scraped_at TEXT
            )
        """)
        
        # 2. Telegram topic threads mapping table
        conn.execute("""
            CREATE TABLE IF NOT EXISTS topic_threads (
                topic TEXT PRIMARY KEY,
                thread_id INTEGER,
                linked_by TEXT,
                linked_at TEXT
            )
        """)
        
        # Indexes for fast search
        conn.execute("CREATE INDEX IF NOT EXISTS idx_jobs_source ON jobs(source)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_jobs_date ON jobs(date)")
        conn.commit()
    finally:
        conn.close()


# Auto-initialize database tables on boot
init_db()


def load_jobs() -> List[Job]:
    """Load all jobs from the SQLite database ordered by date (latest first)."""
    conn = sqlite3.connect(DB_FILE)
    jobs: List[Job] = []
    try:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM jobs ORDER BY date DESC")
        rows = cursor.fetchall()
        for row in rows:
            try:
                # Deserialize tags
                tags_raw = row["tags"]
                tags = json.loads(tags_raw) if tags_raw else []
                
                # Deserialize visa_sponsorship
                visa_val = row["visa_sponsorship"]
                visa = True if visa_val == 1 else (False if visa_val == 0 else None)
                
                # Parse date
                date_str = row["date"]
                dt = datetime.fromisoformat(date_str) if date_str else None
                
                job = Job(
                    id=row["id"],
                    title=row["title"],
                    company=row["company"],
                    location=row["location"],
                    url=row["url"],
                    description=row["description"],
                    source=row["source"],
                    date=dt,
                    tags=tags,
                    match_score=row["match_score"],
                    yoe_min=row["yoe_min"],
                    yoe_max=row["yoe_max"],
                    salary_min=row["salary_min"],
                    salary_max=row["salary_max"],
                    currency=row["currency"],
                    visa_sponsorship=visa,
                    job_type=row["job_type"]
                )
                jobs.append(job)
            except Exception as e:
                print(f"Warning: Failed to parse job from DB: {e}")
    finally:
        conn.close()
    return jobs


def save_jobs(jobs: List[Job]) -> None:
    """Save a list of jobs into the SQLite database, updating existing ones on conflict."""
    conn = sqlite3.connect(DB_FILE)
    try:
        now_str = datetime.utcnow().isoformat() + "Z"
        for j in jobs:
            if not j.id:
                continue
                
            # Serialize tags
            tags_json = json.dumps(j.tags) if j.tags else None
            
            # Serialize visa_sponsorship
            visa_int = 1 if j.visa_sponsorship is True else (0 if j.visa_sponsorship is False else None)
            
            # Serialize date
            date_str = None
            if j.date:
                if isinstance(j.date, datetime):
                    date_str = j.date.isoformat()
                else:
                    date_str = str(j.date)
            
            conn.execute("""
                INSERT INTO jobs (
                    id, title, company, location, url, description, source, date, tags,
                    match_score, yoe_min, yoe_max, salary_min, salary_max, currency,
                    visa_sponsorship, job_type, scraped_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    title=excluded.title,
                    company=excluded.company,
                    location=excluded.location,
                    url=excluded.url,
                    description=excluded.description,
                    source=excluded.source,
                    date=excluded.date,
                    tags=excluded.tags,
                    match_score=excluded.match_score,
                    yoe_min=excluded.yoe_min,
                    yoe_max=excluded.yoe_max,
                    salary_min=excluded.salary_min,
                    salary_max=excluded.salary_max,
                    currency=excluded.currency,
                    visa_sponsorship=excluded.visa_sponsorship,
                    job_type=excluded.job_type,
                    scraped_at=excluded.scraped_at
            """, (
                j.id, j.title, j.company, j.location, j.url, j.description, j.source, date_str, tags_json,
                j.match_score, j.yoe_min, j.yoe_max, j.salary_min, j.salary_max, j.currency,
                visa_int, j.job_type, now_str
            ))
        conn.commit()
    finally:
        conn.close()


def load_saved_at() -> str | None:
    """Return ISO timestamp string of the last save from jobs table."""
    conn = sqlite3.connect(DB_FILE)
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT MAX(scraped_at) FROM jobs")
        row = cursor.fetchone()
        return row[0] if row else None
    finally:
        conn.close()
