"""
Match scoring, visa detection, YOE extraction, and skill matching utilities.
"""
from __future__ import annotations

import re
from typing import Optional, Tuple


# Role tiers (from PREFERENCES.md)
TIER_1_ROLES = [
    "data analyst", "senior data analyst", "senior analyst", "business analyst",
    "product analyst", "decision scientist", "bi developer", "analytics engineer",
    "bi analyst", "financial analyst", "marketing analyst", "operations analyst",
]

TIER_2_ROLES = [
    "junior data scientist", "associate data scientist", "data scientist",
    "ml engineer", "machine learning engineer", "junior ml engineer",
    "associate ml engineer", "junior data engineer", "associate data engineer",
]

# Skill keywords (for skill-based matching)
SKILL_KEYWORDS = [
    "python", "sql", "tableau", "power bi", "looker", "visualization",
    "machine learning", "ml modeling", "statistics", "a/b testing",
    "experimentation", "analytics", "reporting", "dashboards", "etl",
    "data pipeline", "pandas", "numpy", "scikit-learn", "tensorflow",
    "pytorch", "r language", "excel", "spreadsheet",
]

# Visa sponsorship keywords
VISA_KEYWORDS = [
    "visa sponsorship", "sponsored visa", "visa sponsor", "relocation support",
    "relocation assistance", "work visa", "sponsor visa", "visa available",
    "will sponsor", "can sponsor", "sponsorship available",
]

# Location preferences (priority order)
REMOTE_KEYWORDS = ["remote", "work from home", "wfh", "distributed", "anywhere"]
INDIA_REMOTE_KEYWORDS = ["remote india", "india remote", "work from india"]
INDIAN_CITIES = [
    "pune", "hyderabad", "mumbai", "thane", "navi mumbai", "bangalore",
    "chennai", "delhi", "ncr", "gurgaon", "noida",
]


def extract_yoe(text: str) -> Tuple[Optional[int], Optional[int]]:
    """
    Extract years of experience (YOE) from job description.
    Returns (min_yoe, max_yoe) or (None, None) if not found.
    
    Patterns: "2-3 years", "2+ years", "minimum 2 years", "3-5 YOE", etc.
    """
    text_lower = text.lower()
    
    # Pattern: "2-3 years", "2 to 3 years", "2-3 YOE"
    range_pattern = r'(\d+)\s*[-–—to]\s*(\d+)\s*(?:years?|yrs?|yoe|experience)'
    match = re.search(range_pattern, text_lower)
    if match:
        return (int(match.group(1)), int(match.group(2)))
    
    # Pattern: "2+ years", "minimum 2 years", "at least 2 years"
    min_pattern = r'(?:minimum|min|at least|atleast)\s*(\d+)\s*(?:years?|yrs?|yoe|experience)'
    match = re.search(min_pattern, text_lower)
    if match:
        min_yoe = int(match.group(1))
        return (min_yoe, None)
    
    # Pattern: "2-3", "3-5" (standalone numbers)
    simple_range = r'(\d+)\s*[-–—to]\s*(\d+)'
    match = re.search(simple_range, text_lower)
    if match:
        val1, val2 = int(match.group(1)), int(match.group(2))
        if val1 <= 10 and val2 <= 10:  # Reasonable YOE range
            return (val1, val2)
    
    # Pattern: "5+ years" (explicit max)
    plus_pattern = r'(\d+)\+\s*(?:years?|yrs?|yoe|experience)'
    match = re.search(plus_pattern, text_lower)
    if match:
        min_yoe = int(match.group(1))
        return (min_yoe, None)
    
    return (None, None)


def detect_visa_sponsorship(text: str) -> bool:
    """Detect if job mentions visa sponsorship."""
    text_lower = text.lower()
    return any(keyword in text_lower for keyword in VISA_KEYWORDS)


def extract_salary_currency(text: str) -> Tuple[Optional[float], Optional[float], Optional[str]]:
    """
    Extract salary range and currency from job description.
    Returns (min_salary, max_salary, currency_code) or (None, None, None).
    
    Patterns: "$50k-70k", "₹10L-15L", "£30k-40k", "50,000 - 70,000 USD", etc.
    """
    text_lower = text.lower()
    
    # Currency symbols/codes
    currency_map = {
        "$": "USD", "usd": "USD", "dollar": "USD",
        "₹": "INR", "rs": "INR", "inr": "INR", "rupee": "INR", "lakh": "INR", "lpa": "INR",
        "£": "GBP", "gbp": "GBP", "pound": "GBP",
        "€": "EUR", "eur": "EUR", "euro": "EUR",
        "sgd": "SGD", "singapore": "SGD",
        "aed": "AED", "dirham": "AED",
    }
    
    detected_currency = None
    for symbol, code in currency_map.items():
        if symbol in text_lower:
            detected_currency = code
            break
    
    # Pattern: "$50k-70k", "₹10L-15L", "£30k-40k"
    k_pattern = r'(\d+(?:\.\d+)?)\s*k\s*[-–—to]?\s*(\d+(?:\.\d+)?)\s*k'
    match = re.search(k_pattern, text_lower)
    if match:
        min_val = float(match.group(1)) * 1000
        max_val = float(match.group(2)) * 1000
        return (min_val, max_val, detected_currency or "USD")
    
    # Pattern: "₹10L-15L" (Lakhs)
    l_pattern = r'(\d+(?:\.\d+)?)\s*l\s*[-–—to]?\s*(\d+(?:\.\d+)?)\s*l'
    match = re.search(l_pattern, text_lower)
    if match:
        min_val = float(match.group(1)) * 100000
        max_val = float(match.group(2)) * 100000
        return (min_val, max_val, detected_currency or "INR")
    
    # Pattern: "50,000 - 70,000"
    num_pattern = r'(\d{1,3}(?:,\d{3})*(?:\.\d+)?)\s*[-–—to]?\s*(\d{1,3}(?:,\d{3})*(?:\.\d+)?)'
    match = re.search(num_pattern, text_lower)
    if match:
        min_val = float(match.group(1).replace(",", ""))
        max_val = float(match.group(2).replace(",", ""))
        if min_val > 1000 and max_val > 1000:  # Reasonable salary range
            return (min_val, max_val, detected_currency)
    
    return (None, None, detected_currency)


def calculate_match_score(
    job_title: str,
    job_description: str,
    job_location: str,
    job_yoe_min: Optional[int] = None,
    job_yoe_max: Optional[int] = None,
    target_yoe: int = 2,  # Default target: 2-3 YOE
) -> float:
    """
    Calculate match score (0-100) based on role tier, skills, location, YOE.
    
    Scoring breakdown:
    - Role match: 0-40 points (Tier 1 = 40, Tier 2 = 30, skill match = 20, other = 0)
    - Location match: 0-30 points (Remote = 30, Remote India = 25, Indian city = 20, other = 10)
    - YOE match: 0-30 points (Perfect match = 30, close = 20, mismatch = 0-10)
    """
    score = 0.0
    text = f"{job_title} {job_description} {job_location}".lower()
    
    # Role match (0-40 points)
    title_lower = job_title.lower()
    if any(role in title_lower for role in TIER_1_ROLES):
        score += 40
    elif any(role in title_lower for role in TIER_2_ROLES):
        score += 30
    elif any(skill in text for skill in SKILL_KEYWORDS):
        score += 20  # Skill-based match (Python, SQL, etc. even if not "data" title)
    
    # Location match (0-30 points)
    location_lower = job_location.lower()
    if any(kw in location_lower for kw in REMOTE_KEYWORDS):
        score += 30
    elif any(kw in location_lower for kw in INDIA_REMOTE_KEYWORDS):
        score += 25
    elif any(city in location_lower for city in INDIAN_CITIES):
        score += 20
    else:
        score += 10  # Other locations
    
    # YOE match (0-30 points)
    if job_yoe_min is not None or job_yoe_max is not None:
        if job_yoe_min is not None and job_yoe_max is not None:
            # Range match: target should be within range
            if job_yoe_min <= target_yoe <= job_yoe_max:
                score += 30
            elif job_yoe_min <= target_yoe + 1 <= job_yoe_max:
                score += 20
            elif job_yoe_max >= 5:
                score += 0  # Exclude 5+ YOE
            else:
                score += 10
        elif job_yoe_min is not None:
            if job_yoe_min <= target_yoe:
                if job_yoe_min >= 5:
                    score += 0  # Exclude 5+ YOE
                elif job_yoe_min <= target_yoe + 1:
                    score += 25
                else:
                    score += 10
        elif job_yoe_max is not None:
            if job_yoe_max >= target_yoe:
                if job_yoe_max >= 5:
                    score += 0
                else:
                    score += 25
    else:
        score += 15  # No YOE specified - neutral
    
    return min(100.0, max(0.0, score))


def enhance_job_with_metadata(job_description: str, job_location: str) -> dict:
    """
    Extract metadata from job description and location.
    Returns dict with yoe_min, yoe_max, visa_sponsorship, salary_min, salary_max, currency.
    """
    text = f"{job_description} {job_location}"
    
    yoe_min, yoe_max = extract_yoe(text)
    visa = detect_visa_sponsorship(text)
    salary_min, salary_max, currency = extract_salary_currency(text)
    
    return {
        "yoe_min": yoe_min,
        "yoe_max": yoe_max,
        "visa_sponsorship": visa if visa else None,
        "salary_min": salary_min,
        "salary_max": salary_max,
        "currency": currency,
    }
