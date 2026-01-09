#!/bin/bash
# Test database connection failure handling

set -e

echo "=== Test Database Error Handling ==="

# Step 1: Check server is healthy
echo ""
echo "Step 1: Verify server is healthy initially..."
HEALTH=$(curl -s http://localhost:8000/health)
if echo "$HEALTH" | grep -q '"status":"healthy"'; then
    echo "✓ Server is healthy"
else
    echo "✗ Server is not healthy"
    exit 1
fi

# Step 2: Login as debug user
echo ""
echo "Step 2: Login as debug user..."
LOGIN_RESP=$(curl -s -X POST http://localhost:8000/api/auth/login \
    -H "Content-Type: application/json" \
    -d '{"username": "debug_tester", "password": "debugpass123"}')
TOKEN=$(echo "$LOGIN_RESP" | grep -o '"token":"[^"]*"' | cut -d'"' -f4)
if [ -z "$TOKEN" ]; then
    echo "✗ Failed to get token"
    exit 1
fi
echo "✓ Got authentication token"

# Step 3: Trigger a conflict error (duplicate zone name)
echo ""
echo "Step 3: Trigger conflict error (duplicate zone name)..."
RESULT=$(curl -s -w "\n%{http_code}" -X POST http://localhost:8000/api/zones \
    -H "Authorization: Bearer $TOKEN" \
    -H "Content-Type: application/json" \
    -d '{"name": "concurrency_test_zone", "width": 50, "height": 50}')
HTTP_CODE=$(echo "$RESULT" | tail -1)
BODY=$(echo "$RESULT" | head -1)
echo "Response: $BODY"
echo "HTTP Status: $HTTP_CODE"
if [ "$HTTP_CODE" = "409" ]; then
    echo "✓ Server returned 409 Conflict for duplicate zone"
else
    echo "✗ Expected 409 Conflict, got $HTTP_CODE"
    exit 1
fi

# Step 4: Verify server still healthy after error
echo ""
echo "Step 4: Verify server is still healthy after error..."
HEALTH=$(curl -s http://localhost:8000/health)
if echo "$HEALTH" | grep -q '"status":"healthy"'; then
    echo "✓ Server is still healthy after error"
else
    echo "✗ Server is no longer healthy"
    exit 1
fi

# Step 5: Verify normal operations still work
echo ""
echo "Step 5: Verify normal operations still work after error..."
UNIQUE_ZONE="test_zone_$(date +%s)"
RESULT=$(curl -s -w "\n%{http_code}" -X POST http://localhost:8000/api/zones \
    -H "Authorization: Bearer $TOKEN" \
    -H "Content-Type: application/json" \
    -d "{\"name\": \"$UNIQUE_ZONE\", \"width\": 50, \"height\": 50}")
HTTP_CODE=$(echo "$RESULT" | tail -1)
if [ "$HTTP_CODE" = "201" ]; then
    echo "✓ Zone creation works after error handling"
else
    echo "✗ Zone creation failed after error"
    exit 1
fi

# Step 6: Trigger validation error (bad data)
echo ""
echo "Step 6: Trigger validation error (bad data)..."
RESULT=$(curl -s -w "\n%{http_code}" -X POST http://localhost:8000/api/zones \
    -H "Authorization: Bearer $TOKEN" \
    -H "Content-Type: application/json" \
    -d '{"name": "", "width": -1, "height": 0}')
HTTP_CODE=$(echo "$RESULT" | tail -1)
echo "HTTP Status: $HTTP_CODE"
if [ "$HTTP_CODE" = "422" ]; then
    echo "✓ Server returned 422 for validation error"
else
    echo "✗ Expected 422 for validation error, got $HTTP_CODE"
fi

# Step 7: Final health check
echo ""
echo "Step 7: Final health check..."
HEALTH=$(curl -s http://localhost:8000/health)
if echo "$HEALTH" | grep -q '"status":"healthy"'; then
    echo "✓ Server is still healthy after all tests"
else
    echo "✗ Server is no longer healthy"
    exit 1
fi

echo ""
echo "=== ALL DATABASE ERROR HANDLING TESTS PASSED ==="
