#!/bin/bash

# Daily absence marking script
# This script calls the FastAPI endpoint to mark daily absences

LOG_FILE="/home/ahmed/Desktop/teacher/venv/src/logs/daily_absence.log"
API_URL="http://localhost:8000/admin/mark-daily-absences"

# Create logs directory if it doesn't exist
mkdir -p "/home/ahmed/Desktop/teacher/venv/src/logs"

# Get current timestamp
TIMESTAMP=$(date '+%Y-%m-%d %H:%M:%S')

echo "[$TIMESTAMP] Starting daily absence marking..." >> "$LOG_FILE"

# You'll need to replace YOUR_TOKEN_HERE with an actual token
# To get a token, login via: POST /assistant/login with username/password
TOKEN="YOUR_TOKEN_HERE"

# Call the API endpoint
RESPONSE=$(curl -s -X POST "$API_URL" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -w "\nHTTP_CODE:%{http_code}")

# Extract HTTP code
HTTP_CODE=$(echo "$RESPONSE" | tail -n1 | sed 's/.*HTTP_CODE://')
RESPONSE_BODY=$(echo "$RESPONSE" | sed '$d')

echo "[$TIMESTAMP] HTTP Code: $HTTP_CODE" >> "$LOG_FILE"
echo "[$TIMESTAMP] Response: $RESPONSE_BODY" >> "$LOG_FILE"

if [ "$HTTP_CODE" = "200" ]; then
    echo "[$TIMESTAMP] Daily absence marking completed successfully" >> "$LOG_FILE"
else
    echo "[$TIMESTAMP] ERROR: Daily absence marking failed with HTTP code $HTTP_CODE" >> "$LOG_FILE"
fi

echo "[$TIMESTAMP] Finished daily absence marking" >> "$LOG_FILE"
echo "----------------------------------------" >> "$LOG_FILE"
