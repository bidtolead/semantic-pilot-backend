#!/bin/bash
# Cleanup script to enforce 20-report limit

BACKEND_URL="${NEXT_PUBLIC_BACKEND_URL:-https://semantic-pilot-backend.onrender.com}"
ADMIN_TOKEN="${1}"

if [ -z "$ADMIN_TOKEN" ]; then
    echo "❌ Error: Admin token required"
    echo "Usage: ./run_cleanup.sh <ADMIN_TOKEN>"
    exit 1
fi

echo "🔄 Calling cleanup endpoint..."
echo "Endpoint: $BACKEND_URL/admin/cleanup/enforce-history-limit"

curl -X POST "$BACKEND_URL/admin/cleanup/enforce-history-limit" \
    -H "Authorization: Bearer $ADMIN_TOKEN" \
    -H "Content-Type: application/json" \
    -w "\n\nStatus: %{http_code}\n"

echo ""
