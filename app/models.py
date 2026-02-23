from __future__ import annotations

from datetime import datetime
from typing import Dict, List, Optional

from pydantic import BaseModel, HttpUrl, Field, ConfigDict


# Safe JSON examples for OpenAPI/Swagger only (no HTML or code)
_JOB_EXAMPLE = {
    "id": "example-1",
    "title": "Data Analyst",
    "company": "Example Corp",
    "location": "Remote",
    "url": "https://example.com/job/1",
    "description": "Analyze data and build reports.",
    "source": "remotive",
    "date": "2025-02-15T12:00:00Z",
    "tags": ["data", "analytics"],
    "match_score": 85.0,
    "yoe_min": 1,
    "yoe_max": 3,
}

_JOBS_RESPONSE_EXAMPLE = {
    "ok": True,
    "count": 1,
    "jobs": [_JOB_EXAMPLE],
    "total": None,
    "page": None,
    "per_page": None,
    "system": None,
    "error": None,
}

_GROUPED_EXAMPLE = {
    "ok": True,
    "currencies": {"USD": [_JOB_EXAMPLE], "INR": []},
    "error": None,
}


class Job(BaseModel):
    model_config = ConfigDict(json_schema_extra={"examples": [_JOB_EXAMPLE]})
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
    # Match score and filtering fields
    match_score: Optional[float] = Field(None, ge=0, le=100, description="Match percentage (0-100)")
    yoe_min: Optional[int] = Field(None, ge=0, description="Minimum years of experience required")
    yoe_max: Optional[int] = Field(None, ge=0, description="Maximum years of experience required")
    salary_min: Optional[float] = Field(None, ge=0, description="Minimum salary")
    salary_max: Optional[float] = Field(None, ge=0, description="Maximum salary")
    currency: Optional[str] = Field(None, description="Currency code (INR, USD, GBP, etc.)")
    visa_sponsorship: Optional[bool] = Field(None, description="Visa sponsorship available")
    job_type: Optional[str] = Field(None, description="Job type (full_time, contract, part_time, internship)")


class SystemStats(BaseModel):
    """System resource usage stats."""
    cpu_percent: Optional[float] = None
    memory_percent: Optional[float] = None
    memory_used_mb: Optional[float] = None
    memory_total_mb: Optional[float] = None
    disk_percent: Optional[float] = None
    disk_used_gb: Optional[float] = None
    disk_total_gb: Optional[float] = None
    process_memory_mb: Optional[float] = None


class JobsResponse(BaseModel):
    model_config = ConfigDict(json_schema_extra={"examples": [_JOBS_RESPONSE_EXAMPLE]})
    ok: bool = True
    count: int
    jobs: List[Job]
    # Pagination (optional; set when page/per_page are used)
    total: Optional[int] = None
    page: Optional[int] = None
    per_page: Optional[int] = None
    # System stats (optional; included when include_stats=true)
    system: Optional[SystemStats] = None
    # Error message (when ok=False)
    error: Optional[str] = None


class GroupedByCurrencyResponse(BaseModel):
    """Response for /jobs/grouped-by-currency."""
    model_config = ConfigDict(json_schema_extra={"examples": [_GROUPED_EXAMPLE]})
    ok: bool = True
    currencies: Dict[str, List[Job]] = Field(default_factory=dict)  # { "USD": [Job,...], "INR": [Job,...] }
    error: Optional[str] = None
