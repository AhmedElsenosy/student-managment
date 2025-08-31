#!/bin/bash

# Daily absence marking script - Server Deployment Version
# This script calls the FastAPI endpoint to mark daily absences

# Get the directory where this script is located
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Configuration - Update these for your server
API_BASE_URL="${API_BASE_URL:-http://localhost:8000}"
LOG_DIR="${LOG_DIR:-$SCRIPT_DIR/logs}"
LOG_FILE="$LOG_DIR/daily_absence.log"
API_URL="$API_BASE_URL/admin/mark-daily-absences"

# Authentication - Use environment variable or fallback
AUTH_TOKEN="${DAILY_ABSENCE_TOKEN:-YOUR_TOKEN_HERE}"

# Create logs directory if it doesn't exist
mkdir -p "$LOG_DIR"

# Get current timestamp
TIMESTAMP=$(date '+%Y-%m-%d %H:%M:%S')

echo "[$TIMESTAMP] Starting daily absence marking..." >> "$LOG_FILE"
echo "[$TIMESTAMP] API URL: $API_URL" >> "$LOG_FILE"

# Check if token is set
if [ "$AUTH_TOKEN" = "YOUR_TOKEN_HERE" ]; then
    echo "[$TIMESTAMP] ERROR: Authentication token not configured!" >> "$LOG_FILE"
    echo "[$TIMESTAMP] Please set DAILY_ABSENCE_TOKEN environment variable" >> "$LOG_FILE"
    exit 1
fi

# Check if curl is available
if ! command -v curl &> /dev/null; then
    echo "[$TIMESTAMP] ERROR: curl command not found!" >> "$LOG_FILE"
    exit 1
fi

# Call the API endpoint with timeout
RESPONSE=$(curl -s --max-time 30 -X POST "$API_URL" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $AUTH_TOKEN" \
  -w "\nHTTP_CODE:%{http_code}" 2>&1)

CURL_EXIT_CODE=$?

# Check if curl command succeeded
if [ $CURL_EXIT_CODE -ne 0 ]; then
    echo "[$TIMESTAMP] ERROR: curl command failed with exit code $CURL_EXIT_CODE" >> "$LOG_FILE"
    echo "[$TIMESTAMP] Response: $RESPONSE" >> "$LOG_FILE"
    exit 1
fi

# Extract HTTP code
HTTP_CODE=$(echo "$RESPONSE" | tail -n1 | sed 's/.*HTTP_CODE://')
RESPONSE_BODY=$(echo "$RESPONSE" | sed '$d')

echo "[$TIMESTAMP] HTTP Code: $HTTP_CODE" >> "$LOG_FILE"
echo "[$TIMESTAMP] Response: $RESPONSE_BODY" >> "$LOG_FILE"

if [ "$HTTP_CODE" = "200" ]; then
    echo "[$TIMESTAMP] ✅ Daily absence marking completed successfully" >> "$LOG_FILE"
    exit 0
else
    echo "[$TIMESTAMP] ❌ ERROR: Daily absence marking failed with HTTP code $HTTP_CODE" >> "$LOG_FILE"
    exit 1
fi

echo "[$TIMESTAMP] Finished daily absence marking" >> "$LOG_FILE"
echo "----------------------------------------" >> "$LOG_FILE"
