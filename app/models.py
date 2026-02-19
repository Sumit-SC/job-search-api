from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, HttpUrl, Field


class Job(BaseModel):
    id: str
    title: str
    company: str
    location: str
    url: HttpUrl
    description: str = ""
    source: str
    date: Optional[datetime] = None
    tags: List[str] = Field(default_factory=list)
    # Optional metadata for ranking / UI
    date_formatted: Optional[str] = None
    posted_ago: Optional[str] = None
    rank: float = 0.0


class JobsResponse(BaseModel):
    ok: bool = True
    count: int
    jobs: List[Job]
    # Pagination (optional; set when page/per_page are used)
    total: Optional[int] = None
    page: Optional[int] = None
    per_page: Optional[int] = None
