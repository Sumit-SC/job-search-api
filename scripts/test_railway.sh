#!/bin/bash
# Test script for Railway deployment
# Usage: ./test_railway.sh https://your-app.up.railway.app

BASE_URL="${1:-http://localhost:8000}"

echo "Testing Railway deployment at: $BASE_URL"
echo "=========================================="
echo ""

# Test health endpoint
echo "1. Testing /health..."
HEALTH=$(curl -s "$BASE_URL/health")
if echo "$HEALTH" | grep -q '"ok":true'; then
    echo "✅ Health check passed"
else
    echo "❌ Health check failed"
    echo "Response: $HEALTH"
    exit 1
fi
echo ""

# Test system endpoint
echo "2. Testing /system..."
SYSTEM=$(curl -s "$BASE_URL/system")
if echo "$SYSTEM" | grep -q '"ok":true'; then
    echo "✅ System endpoint working"
    echo "$SYSTEM" | python3 -m json.tool 2>/dev/null || echo "$SYSTEM"
else
    echo "⚠️  System endpoint returned non-ok status"
    echo "$SYSTEM"
fi
echo ""

# Test debug RSS scrapers
echo "3. Testing /debug (RSS scrapers)..."
DEBUG=$(curl -s "$BASE_URL/debug")
if echo "$DEBUG" | grep -q '"ok":true'; then
    echo "✅ RSS scrapers test passed"
    SCRAPER_COUNT=$(echo "$DEBUG" | python3 -c "import sys, json; data=json.load(sys.stdin); print(len(data.get('scrapers', {})))" 2>/dev/null || echo "0")
    echo "   Found $SCRAPER_COUNT scrapers"
else
    echo "⚠️  Debug endpoint issue"
    echo "$DEBUG"
fi
echo ""

# Test refresh endpoint (RSS only, fast)
echo "4. Testing /refresh?headless=0 (RSS only)..."
REFRESH=$(curl -s -X POST "$BASE_URL/refresh?q=data%20analyst&days=3&headless=0")
if echo "$REFRESH" | grep -q '"ok":true'; then
    echo "✅ Refresh endpoint working (RSS only)"
    JOB_COUNT=$(echo "$REFRESH" | python3 -c "import sys, json; data=json.load(sys.stdin); print(len(data.get('jobs', [])))" 2>/dev/null || echo "0")
    echo "   Scraped $JOB_COUNT jobs"
else
    echo "⚠️  Refresh endpoint issue"
    echo "$REFRESH"
fi
echo ""

# Test jobs endpoint
echo "5. Testing /jobs..."
JOBS=$(curl -s "$BASE_URL/jobs?limit=10")
if echo "$JOBS" | grep -q '"ok":true'; then
    echo "✅ Jobs endpoint working"
    JOB_COUNT=$(echo "$JOBS" | python3 -c "import sys, json; data=json.load(sys.stdin); print(len(data.get('jobs', [])))" 2>/dev/null || echo "0")
    echo "   Retrieved $JOB_COUNT jobs"
else
    echo "⚠️  Jobs endpoint issue"
    echo "$JOBS"
fi
echo ""

echo "=========================================="
echo "✅ All basic tests completed!"
echo ""
echo "To test headless scrapers (slower):"
echo "  curl -X POST '$BASE_URL/refresh?q=data%20analyst&days=3'"
echo ""
echo "To test headless debug endpoint:"
echo "  curl '$BASE_URL/debug/headless'"
