#!/usr/bin/env bash
# Test job-search-api endpoints (local or deployed).
# Usage: ./test_endpoints.sh [BASE_URL]
# Example: ./test_endpoints.sh https://your-app.up.railway.app

BASE_URL="${1:-http://localhost:8000}"
BASE_URL="${BASE_URL%/}"

echo "Testing API at $BASE_URL"
echo ""

# 1. Health
echo "1. GET /health"
curl -sS "$BASE_URL/health" | head -c 200
echo ""
echo ""

# 2. Debug (all 11 RSS scrapers)
echo "2. GET /debug (RSS/HTTP scrapers)"
curl -sS "$BASE_URL/debug" | python3 -c "
import sys, json
d = json.load(sys.stdin)
print('   ok:', d.get('ok'), ', total_jobs:', d.get('total_jobs'))
for k, v in (d.get('scrapers') or {}).items():
    status = 'ok' if v.get('ok') else 'err'
    print('   -', k, ': count=' + str(v.get('count', 0)), status)
" 2>/dev/null || curl -sS "$BASE_URL/debug"
echo ""
echo ""

# 3. Debug headless (can be slow)
echo "3. GET /debug/headless (LinkedIn, Indeed, Naukri)"
curl -sS --max-time 120 "$BASE_URL/debug/headless" | python3 -c "
import sys, json
d = json.load(sys.stdin)
if d.get('skipped'):
    print('   ', d['skipped'])
elif d.get('error'):
    print('   error:', d['error'])
else:
    print('   ok:', d.get('ok'), ', total_jobs:', d.get('total_jobs'))
    for k, v in (d.get('scrapers') or {}).items():
        status = 'ok' if v.get('ok') else 'err'
        print('   -', k, ': count=' + str(v.get('count', 0)), status)
" 2>/dev/null || echo "   (run curl $BASE_URL/debug/headless for raw response)"
echo ""
echo ""

# 4. Refresh RSS-only
echo "4. POST /refresh?days=3&headless=0 (RSS-only)"
curl -sS -X POST --max-time 120 "$BASE_URL/refresh?days=3&headless=0" | python3 -c "
import sys, json
d = json.load(sys.stdin)
print('   ok:', d.get('ok'), ', count:', d.get('count'))
" 2>/dev/null || echo "   (check response above)"
echo ""
echo ""

# 5. GET jobs
echo "5. GET /jobs?days=7&limit=5"
curl -sS "$BASE_URL/jobs?days=7&limit=5" | python3 -c "
import sys, json
d = json.load(sys.stdin)
print('   ok:', d.get('ok'), ', count:', d.get('count'))
jobs = d.get('jobs') or []
if jobs:
    print('   first job:', jobs[0].get('title'), '@', jobs[0].get('source'))
" 2>/dev/null || echo "   (check response above)"
echo ""
echo "Done."
