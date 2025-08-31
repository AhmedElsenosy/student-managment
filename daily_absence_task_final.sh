#!/bin/bash

# Daily absence marking script - Final Production Version
# Domain: https://offline-sys-api.in-general.net
# No authentication required

# Get the directory where this script is located
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Configuration
API_URL="https://offline-sys-api.in-general.net/admin/mark-daily-absences"
LOG_DIR="$SCRIPT_DIR/logs"
LOG_FILE="$LOG_DIR/daily_absence.log"

# Create logs directory if it doesn't exist
mkdir -p "$LOG_DIR"

# Get current timestamp
TIMESTAMP=$(date '+%Y-%m-%d %H:%M:%S')

echo "[$TIMESTAMP] Starting daily absence marking..." >> "$LOG_FILE"
echo "[$TIMESTAMP] API URL: $API_URL" >> "$LOG_FILE"

# Check if curl is available
if ! command -v curl &> /dev/null; then
    echo "[$TIMESTAMP] ERROR: curl command not found!" >> "$LOG_FILE"
    exit 1
fi

# Call the API endpoint with timeout (no auth required)
RESPONSE=$(curl -s --max-time 30 -X POST "$API_URL" \
  -H "Content-Type: application/json" \
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
