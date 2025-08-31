#!/bin/sh

echo "🚀 Daily Absence Task - Server Setup"
echo "====================================="
echo ""

# Get current directory
CURRENT_DIR=$(pwd)
TASK_SCRIPT="$CURRENT_DIR/daily_absence_task_final.sh"

echo "📍 Current directory: $CURRENT_DIR"
echo ""

# Step 1: Check if the main script exists
echo "[1/5] Checking for daily_absence_task_final.sh..."
if [ ! -f "$TASK_SCRIPT" ]; then
    echo "❌ ERROR: daily_absence_task_final.sh not found in current directory"
    echo "Please make sure daily_absence_task_final.sh is in the same directory as this setup script"
    exit 1
fi
echo "✅ Found: daily_absence_task_final.sh"

# Step 2: Make script executable
echo "[2/5] Making script executable..."
chmod +x "$TASK_SCRIPT"
if [ $? -eq 0 ]; then
    echo "✅ Script is now executable"
else
    echo "❌ Failed to make script executable"
    exit 1
fi

# Step 3: Check if curl is available
echo "[3/5] Checking system requirements..."
if ! command -v curl > /dev/null 2>&1; then
    echo "❌ curl is not installed"
    echo "Installing curl..."
    
    if command -v apt-get > /dev/null 2>&1; then
        sudo apt-get update && sudo apt-get install -y curl
    elif command -v yum > /dev/null 2>&1; then
        sudo yum install -y curl
    else
        echo "❌ Could not install curl automatically. Please install curl manually."
        exit 1
    fi
fi
echo "✅ curl is available"

# Step 4: Test the API connection
echo "[4/5] Testing API connection..."
API_URL="https://offline-sys-api.in-general.net"
if curl -s --max-time 10 "$API_URL" > /dev/null 2>&1; then
    echo "✅ API server is reachable"
else
    echo "⚠️  API server test failed (might be normal if server is not running)"
    echo "ℹ️  The task will still be scheduled and will work when your server is running"
fi

# Step 5: Set up cron job
echo "[5/5] Setting up daily cron job (11:59 PM)..."

# Remove any existing daily absence cron jobs to avoid duplicates
crontab -l 2>/dev/null | grep -v "daily_absence_task" > /tmp/current_cron 2>/dev/null || touch /tmp/current_cron

# Add the new cron job
echo "59 23 * * * $TASK_SCRIPT" >> /tmp/current_cron
crontab /tmp/current_cron
rm -f /tmp/current_cron

if [ $? -eq 0 ]; then
    echo "✅ Cron job scheduled successfully"
else
    echo "❌ Failed to set up cron job"
    exit 1
fi

# Create logs directory
LOG_DIR="$CURRENT_DIR/logs"
mkdir -p "$LOG_DIR"
echo "✅ Log directory created: $LOG_DIR"

# Final summary
echo ""
echo "🎉 SETUP COMPLETE!"
echo "=================="
echo ""
echo "📋 Configuration Summary:"
echo "• Script: $TASK_SCRIPT"
echo "• API URL: https://offline-sys-api.in-general.net/admin/mark-daily-absences"
echo "• Schedule: Every day at 11:59 PM"
echo "• Logs: $LOG_DIR/daily_absence.log"
echo "• Authentication: None (removed as requested)"
echo ""

echo "🔍 Useful Commands:"
echo "• Test manually: $TASK_SCRIPT"
echo "• View logs: tail -f $LOG_DIR/daily_absence.log"
echo "• Check cron jobs: crontab -l"
echo "• Remove cron job: crontab -e (then delete the line)"
echo ""

echo "📅 Next Execution:"
NEXT_RUN=$(date -d "today 23:59" '+%Y-%m-%d %H:%M:%S' 2>/dev/null || date '+%Y-%m-%d 23:59:00')
echo "• $NEXT_RUN (if today hasn't passed 11:59 PM yet)"
echo ""

echo "💡 Want to test right now?"
printf "Run the daily absence task immediately? (y/n): "
read REPLY
echo ""
if [ "$REPLY" = "y" ] || [ "$REPLY" = "Y" ]; then
    echo ""
    echo "🧪 Running test..."
    echo "=================="
    "$TASK_SCRIPT"
    echo ""
    echo "📊 Test completed. Check the logs:"
    echo "tail -f $LOG_DIR/daily_absence.log"
fi

echo ""
echo "✅ Daily Absence Task is now fully configured and ready!"
echo "🚀 The task will automatically run every day at 11:59 PM"
