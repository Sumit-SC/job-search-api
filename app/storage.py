from __future__ import annotations

import os
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional, Tuple

from .models import Job

# Unify data directory and SQLite DB file
DATA_DIR = Path(os.environ.get("JOBS_SCRAPER_DATA_DIR", "data"))
DB_FILE = DATA_DIR / "jobs.db"


def execute_write(sql: str, params: tuple = ()) -> None:
    """Execute a write command on Turso if configured, falling back to local SQLite."""
    url = os.environ.get("TURSO_DATABASE_URL", "").strip()
    token = os.environ.get("TURSO_AUTH_TOKEN", "").strip()
    
    if url and token:
        try:
            import libsql_client
            with libsql_client.create_client_sync(url=url, auth_token=token) as client:
                client.execute(sql, params)
                return
        except Exception as e:
            print(f"ERROR: Turso write failed: {e}. Falling back to local SQLite.")
            
    conn = sqlite3.connect(DB_FILE)
    try:
        conn.execute(sql, params)
        conn.commit()
    except Exception as e:
        print(f"ERROR: Local SQLite write failed: {e}")
        raise e
    finally:
        conn.close()


def execute_read(sql: str, params: tuple = ()) -> list[dict]:
    """Execute a read query on Turso if configured, falling back to local SQLite."""
    url = os.environ.get("TURSO_DATABASE_URL", "").strip()
    token = os.environ.get("TURSO_AUTH_TOKEN", "").strip()
    
    if url and token:
        try:
            import libsql_client
            with libsql_client.create_client_sync(url=url, auth_token=token) as client:
                rs = client.execute(sql, params)
                out = []
                for row in rs.rows:
                    out.append({col: row[idx] for idx, col in enumerate(rs.columns)})
                return out
        except Exception as e:
            print(f"ERROR: Turso read failed: {e}. Falling back to local SQLite.")
            
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    try:
        cursor = conn.cursor()
        cursor.execute(sql, params)
        rows = cursor.fetchall()
        return [dict(r) for r in rows]
    except Exception as e:
        print(f"ERROR: Local SQLite read failed: {e}")
        raise e
    finally:
        conn.close()


def execute_batch_write(statements: list[tuple[str, tuple]]) -> None:
    """Execute a batch of write statements on Turso if configured, falling back to local SQLite."""
    if not statements:
        return
    url = os.environ.get("TURSO_DATABASE_URL", "").strip()
    token = os.environ.get("TURSO_AUTH_TOKEN", "").strip()
    
    if url and token:
        try:
            import libsql_client
            with libsql_client.create_client_sync(url=url, auth_token=token) as client:
                client.batch(statements)
                return
        except Exception as e:
            print(f"ERROR: Turso batch write failed: {e}. Falling back to local SQLite.")
            
    conn = sqlite3.connect(DB_FILE)
    try:
        cursor = conn.cursor()
        for sql, params in statements:
            cursor.execute(sql, params)
        conn.commit()
    except Exception as e:
        print(f"ERROR: Local SQLite batch write failed: {e}")
        raise e
    finally:
        conn.close()


def init_db() -> None:
    """Initialize database tables and indexes."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    
    # 1. Job listings table
    execute_write("""
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
    execute_write("""
        CREATE TABLE IF NOT EXISTS topic_threads (
            topic TEXT PRIMARY KEY,
            thread_id INTEGER,
            linked_by TEXT,
            linked_at TEXT
        )
    """)
    
    # 3. User Profiles table for personalized ranking
    execute_write("""
        CREATE TABLE IF NOT EXISTS user_profiles (
            user_id INTEGER PRIMARY KEY,
            first_name TEXT,
            yoe INTEGER,
            skills TEXT, -- Comma-separated skills
            locations TEXT -- Comma-separated locations
        )
    """)
    
    # Indexes
    try:
        execute_write("CREATE INDEX IF NOT EXISTS idx_jobs_source ON jobs(source)")
        execute_write("CREATE INDEX IF NOT EXISTS idx_jobs_date ON jobs(date)")
    except Exception:
        pass


# Auto-initialize database on startup
init_db()


def load_jobs() -> List[Job]:
    """Load all jobs from database ordered by date (latest first)."""
    rows = execute_read("SELECT * FROM jobs ORDER BY date DESC")
    jobs: List[Job] = []
    for row in rows:
        try:
            # Deserialize tags
            tags_raw = row.get("tags")
            tags = json.loads(tags_raw) if tags_raw else []
            
            # Deserialize visa_sponsorship
            visa_val = row.get("visa_sponsorship")
            visa = True if visa_val == 1 else (False if visa_val == 0 else None)
            
            # Parse date
            date_str = row.get("date")
            dt = datetime.fromisoformat(date_str) if date_str else None
            
            job = Job(
                id=row.get("id"),
                title=row.get("title"),
                company=row.get("company"),
                location=row.get("location"),
                url=row.get("url"),
                description=row.get("description"),
                source=row.get("source"),
                date=dt,
                tags=tags,
                match_score=row.get("match_score"),
                yoe_min=row.get("yoe_min"),
                yoe_max=row.get("yoe_max"),
                salary_min=row.get("salary_min"),
                salary_max=row.get("salary_max"),
                currency=row.get("currency"),
                visa_sponsorship=visa,
                job_type=row.get("job_type")
            )
            jobs.append(job)
        except Exception as e:
            print(f"Warning: Failed to parse job from DB: {e}")
    return jobs


def save_jobs(jobs: List[Job]) -> None:
    """Save a list of jobs, updating existing ones on conflict."""
    now_str = datetime.utcnow().isoformat() + "Z"
    statements = []
    for j in jobs:
        if not j.id:
            continue
            
        tags_json = json.dumps(j.tags) if j.tags else None
        visa_int = 1 if j.visa_sponsorship is True else (0 if j.visa_sponsorship is False else None)
        url_str = str(j.url) if j.url else None
        
        date_str = None
        if j.date:
            if isinstance(j.date, datetime):
                date_str = j.date.isoformat()
            else:
                date_str = str(j.date)
                
        sql = """
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
        """
        params = (
            j.id, j.title, j.company, j.location, url_str, j.description, j.source, date_str, tags_json,
            j.match_score, j.yoe_min, j.yoe_max, j.salary_min, j.salary_max, j.currency,
            visa_int, j.job_type, now_str
        )
        statements.append((sql, params))
        
    execute_batch_write(statements)


def load_saved_at() -> str | None:
    """Return ISO timestamp string of the last save from jobs table."""
    rows = execute_read("SELECT MAX(scraped_at) AS max_scraped FROM jobs")
    if rows and rows[0].get("max_scraped"):
        return rows[0]["max_scraped"]
    return None


def save_user_profile(user_id: int, first_name: str, yoe: int | None, skills: str | None, locations: str | None) -> None:
    """Save or update user search preferences profile."""
    sql = """
        INSERT INTO user_profiles (user_id, first_name, yoe, skills, locations)
        VALUES (?, ?, ?, ?, ?)
        ON CONFLICT(user_id) DO UPDATE SET
            first_name=excluded.first_name,
            yoe=excluded.yoe,
            skills=excluded.skills,
            locations=excluded.locations
    """
    execute_write(sql, (user_id, first_name, yoe, skills, locations))


def get_user_profile(user_id: int) -> dict | None:
    """Retrieve user search preferences."""
    rows = execute_read("SELECT * FROM user_profiles WHERE user_id = ?", (user_id,))
    if rows:
        return rows[0]
    return None


def get_linked_thread_id(topic: str) -> int | None:
    """Get the thread ID linked to a topic."""
    rows = execute_read("SELECT thread_id FROM topic_threads WHERE topic = ?", (topic.lower().strip(),))
    if rows and rows[0].get("thread_id"):
        return int(rows[0]["thread_id"])
    return None


def link_topic_to_thread(topic: str, thread_id: int, user_info: str) -> Tuple[bool, Optional[int]]:
    """Link a topic to a thread ID. Returns: (success, old_thread_id)."""
    topic_clean = topic.lower().strip()
    old_thread = get_linked_thread_id(topic_clean)
    
    now_str = datetime.utcnow().isoformat()
    execute_write("""
        INSERT INTO topic_threads (topic, thread_id, linked_by, linked_at)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(topic) DO UPDATE SET
            thread_id=excluded.thread_id,
            linked_by=excluded.linked_by,
            linked_at=excluded.linked_at
    """, (topic_clean, thread_id, user_info, now_str))
    return True, old_thread


def unlink_topic(topic: str) -> Optional[int]:
    """Unlink a topic. Returns the unlinked thread ID if existed."""
    topic_clean = topic.lower().strip()
    old_thread = get_linked_thread_id(topic_clean)
    if old_thread is None:
        return None
        
    execute_write("DELETE FROM topic_threads WHERE topic = ?", (topic_clean,))
    return old_thread


def get_all_linked_topics() -> List[dict]:
    """Get all topic mappings from DB."""
    return execute_read("SELECT topic, thread_id, linked_by, linked_at FROM topic_threads")
