#!/bin/bash

echo "🚀 Daily Absence Task - Automated Server Setup"
echo "=============================================="
echo ""

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Get current directory
CURRENT_DIR=$(pwd)
TASK_SCRIPT="$CURRENT_DIR/daily_absence_task_final.sh"

echo -e "${BLUE}📍 Current directory: $CURRENT_DIR${NC}"
echo ""

# Step 1: Check if the main script exists
echo -e "${YELLOW}[1/5]${NC} Checking for daily_absence_task_final.sh..."
if [ ! -f "$TASK_SCRIPT" ]; then
    echo -e "${RED}❌ ERROR: daily_absence_task_final.sh not found in current directory${NC}"
    echo "Please make sure daily_absence_task_final.sh is in the same directory as this setup script"
    exit 1
fi
echo -e "${GREEN}✅ Found: daily_absence_task_final.sh${NC}"

# Step 2: Make script executable
echo -e "${YELLOW}[2/5]${NC} Making script executable..."
chmod +x "$TASK_SCRIPT"
if [ $? -eq 0 ]; then
    echo -e "${GREEN}✅ Script is now executable${NC}"
else
    echo -e "${RED}❌ Failed to make script executable${NC}"
    exit 1
fi

# Step 3: Check if curl is available
echo -e "${YELLOW}[3/5]${NC} Checking system requirements..."
if ! command -v curl &> /dev/null; then
    echo -e "${RED}❌ curl is not installed${NC}"
    echo "Installing curl..."
    
    if command -v apt-get &> /dev/null; then
        sudo apt-get update && sudo apt-get install -y curl
    elif command -v yum &> /dev/null; then
        sudo yum install -y curl
    else
        echo -e "${RED}❌ Could not install curl automatically. Please install curl manually.${NC}"
        exit 1
    fi
fi
echo -e "${GREEN}✅ curl is available${NC}"

# Step 4: Test the API connection
echo -e "${YELLOW}[4/5]${NC} Testing API connection..."
API_URL="https://offline-sys-api.in-general.net"
if curl -s --max-time 10 "$API_URL" > /dev/null 2>&1; then
    echo -e "${GREEN}✅ API server is reachable${NC}"
else
    echo -e "${YELLOW}⚠️  API server test failed (might be normal if server is not running)${NC}"
    echo -e "${BLUE}ℹ️  The task will still be scheduled and will work when your server is running${NC}"
fi

# Step 5: Set up cron job
echo -e "${YELLOW}[5/5]${NC} Setting up daily cron job (11:59 PM)..."

# Remove any existing daily absence cron jobs to avoid duplicates
crontab -l 2>/dev/null | grep -v "daily_absence_task" | crontab -

# Add the new cron job
(crontab -l 2>/dev/null; echo "59 23 * * * $TASK_SCRIPT") | crontab -

if [ $? -eq 0 ]; then
    echo -e "${GREEN}✅ Cron job scheduled successfully${NC}"
else
    echo -e "${RED}❌ Failed to set up cron job${NC}"
    exit 1
fi

# Create logs directory
LOG_DIR="$CURRENT_DIR/logs"
mkdir -p "$LOG_DIR"
echo -e "${GREEN}✅ Log directory created: $LOG_DIR${NC}"

# Final summary
echo ""
echo -e "${GREEN}🎉 SETUP COMPLETE!${NC}"
echo "===================="
echo ""
echo -e "${BLUE}📋 Configuration Summary:${NC}"
echo "• Script: $TASK_SCRIPT"
echo "• API URL: https://offline-sys-api.in-general.net/admin/mark-daily-absences"
echo "• Schedule: Every day at 11:59 PM"
echo "• Logs: $LOG_DIR/daily_absence.log"
echo "• Authentication: None (removed as requested)"
echo ""

echo -e "${BLUE}🔍 Useful Commands:${NC}"
echo "• Test manually: $TASK_SCRIPT"
echo "• View logs: tail -f $LOG_DIR/daily_absence.log"
echo "• Check cron jobs: crontab -l"
echo "• Remove cron job: crontab -e (then delete the line)"
echo ""

echo -e "${BLUE}📅 Next Execution:${NC}"
NEXT_RUN=$(date -d "today 23:59" '+%Y-%m-%d %H:%M:%S')
echo "• $NEXT_RUN (if today hasn't passed 11:59 PM yet)"
echo "• Otherwise: $(date -d "tomorrow 23:59" '+%Y-%m-%d %H:%M:%S')"
echo ""

echo -e "${YELLOW}💡 Want to test right now?${NC}"
printf "Run the daily absence task immediately? (y/n): "
read REPLY
echo ""
if [ "$REPLY" = "y" ] || [ "$REPLY" = "Y" ]; then
    echo ""
    echo -e "${BLUE}🧪 Running test...${NC}"
    echo "==================="
    "$TASK_SCRIPT"
    echo ""
    echo -e "${BLUE}📊 Test completed. Check the logs:${NC}"
    echo "tail -f $LOG_DIR/daily_absence.log"
fi

echo ""
echo -e "${GREEN}✅ Daily Absence Task is now fully configured and ready!${NC}"
echo -e "${BLUE}🚀 The task will automatically run every day at 11:59 PM${NC}"
