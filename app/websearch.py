from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

import httpx


@dataclass(frozen=True)
class WebSearchItem:
    title: str
    url: str
    snippet: str = ""
    source: str = "websearch"


class WebSearchError(RuntimeError):
    pass


def _clean_str(v: Any) -> str:
    if v is None:
        return ""
    s = str(v).strip()
    return s


async def _serpapi_search(
    *,
    q: str,
    engine: str,
    num: int,
    location: Optional[str] = None,
) -> List[WebSearchItem]:
    """
    Uses SerpAPI as a universal backend for Google/Bing/etc.
    Requires env var SERPAPI_API_KEY.
    """
    api_key = os.environ.get("SERPAPI_API_KEY", "").strip()
    if not api_key:
        raise WebSearchError("Missing SERPAPI_API_KEY")

    # SerpAPI endpoint
    url = "https://serpapi.com/search.json"

    params: Dict[str, Any] = {
        "api_key": api_key,
        "engine": engine,  # e.g. "google", "bing"
        "q": q,
        "num": max(1, min(int(num), 100)),
    }
    # SerpAPI location is optional and engine-specific; keep as best-effort
    if location:
        params["location"] = location

    async with httpx.AsyncClient(timeout=25) as client:
        r = await client.get(url, params=params)
        r.raise_for_status()
        data = r.json()

    organic = data.get("organic_results") or []
    out: List[WebSearchItem] = []
    for it in organic:
        link = _clean_str(it.get("link") or it.get("url"))
        title = _clean_str(it.get("title"))
        snippet = _clean_str(it.get("snippet") or it.get("description"))
        if not link or not title:
            continue
        out.append(WebSearchItem(title=title, url=link, snippet=snippet, source=f"serpapi:{engine}"))
        if len(out) >= num:
            break
    return out


async def _brave_search(
    *,
    q: str,
    num: int,
) -> List[WebSearchItem]:
    """
    Brave Search API.
    Requires env var BRAVE_SEARCH_API_KEY.
    """
    api_key = os.environ.get("BRAVE_SEARCH_API_KEY", "").strip()
    if not api_key:
        raise WebSearchError("Missing BRAVE_SEARCH_API_KEY")

    url = "https://api.search.brave.com/res/v1/web/search"
    headers = {"X-Subscription-Token": api_key, "Accept": "application/json"}
    params = {"q": q, "count": max(1, min(int(num), 20))}

    async with httpx.AsyncClient(timeout=25) as client:
        r = await client.get(url, headers=headers, params=params)
        r.raise_for_status()
        data = r.json()

    results = (((data or {}).get("web") or {}).get("results")) or []
    out: List[WebSearchItem] = []
    for it in results:
        link = _clean_str(it.get("url"))
        title = _clean_str(it.get("title"))
        snippet = _clean_str(it.get("description"))
        if not link or not title:
            continue
        out.append(WebSearchItem(title=title, url=link, snippet=snippet, source="brave"))
        if len(out) >= num:
            break
    return out


async def websearch_jobs(
    *,
    q: str,
    provider: str = "serpapi",
    engine: str = "google",
    num: int = 10,
    location: Optional[str] = None,
) -> List[WebSearchItem]:
    """
    Web search entrypoint.

    Providers:
    - provider=serpapi (engine=google|bing|...)
    - provider=brave
    """
    q = _clean_str(q)
    if not q:
        return []

    provider = _clean_str(provider).lower() or "serpapi"
    num = max(1, min(int(num), 50))

    if provider == "serpapi":
        eng = _clean_str(engine).lower() or "google"
        return await _serpapi_search(q=q, engine=eng, num=num, location=location)
    if provider == "brave":
        return await _brave_search(q=q, num=num)

    raise WebSearchError(f"Unsupported provider: {provider}")

