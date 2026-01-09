#!/bin/bash
# Test session expiration

set -e

echo "=== Test Session Expiration (5 second timeout) ==="

# Step 1: Login and get token
echo ""
echo "Step 1: Login..."
RESPONSE=$(curl -s -X POST http://localhost:8000/api/auth/login \
    -H "Content-Type: application/json" \
    -d '{"username": "expire_test_v2", "password": "testpass123"}')
TOKEN=$(echo "$RESPONSE" | grep -o '"token":"[^"]*"' | cut -d'"' -f4)
echo "Token obtained: ${TOKEN:0:50}..."

# Step 2: Test immediately (should work)
echo ""
echo "Step 2: Testing token immediately after login..."
RESULT1=$(curl -s -w "\n%{http_code}" http://localhost:8000/api/auth/me \
    -H "Authorization: Bearer $TOKEN")
HTTP_CODE1=$(echo "$RESULT1" | tail -1)
BODY1=$(echo "$RESULT1" | head -1)
echo "Response: $BODY1"
echo "HTTP Status: $HTTP_CODE1"

if [ "$HTTP_CODE1" = "200" ]; then
    echo "✓ SUCCESS: Token works immediately after login"
else
    echo "✗ FAILURE: Token should work immediately"
    exit 1
fi

# Step 3: Wait for expiration (5 second timeout + 1 second buffer)
echo ""
echo "Step 3: Waiting 6 seconds for session to expire..."
sleep 6

# Step 4: Test after expiration (should fail with 401)
echo ""
echo "Step 4: Testing token after expiration..."
RESULT2=$(curl -s -w "\n%{http_code}" http://localhost:8000/api/auth/me \
    -H "Authorization: Bearer $TOKEN")
HTTP_CODE2=$(echo "$RESULT2" | tail -1)
BODY2=$(echo "$RESULT2" | head -1)
echo "Response: $BODY2"
echo "HTTP Status: $HTTP_CODE2"

if [ "$HTTP_CODE2" = "401" ]; then
    echo "✓ SUCCESS: Expired session correctly rejected with 401"
else
    echo "✗ FAILURE: Should get 401 for expired session"
    exit 1
fi

echo ""
echo "=== ALL TESTS PASSED ==="
