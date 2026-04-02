from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path


async def main() -> None:
    # Make `from app...` imports work when running as a script.
    repo_root = Path(__file__).resolve().parents[1]
    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))

    # Ensure we test the "missing key" behavior deterministically
    os.environ.pop("SERPAPI_API_KEY", None)
    os.environ.pop("BRAVE_SEARCH_API_KEY", None)

    from app.main import websearch

    res = await websearch(q="data analyst remote", provider="serpapi", engine="google", limit=3, location=None)
    print("ok=", res.ok)
    print("count=", res.count)
    print("error=", res.error)


if __name__ == "__main__":
    asyncio.run(main())

