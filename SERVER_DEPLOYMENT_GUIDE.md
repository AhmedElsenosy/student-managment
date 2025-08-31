# Server Deployment Guide - Daily Absence Background Task

## 📋 Quick Setup Checklist

### 1. **Copy Files to Server**
Upload these files to your server:
- `daily_absence_task_server.sh` (the updated server-ready script)
- Your FastAPI application

### 2. **Set File Permissions**
```bash
chmod +x /path/to/your/app/daily_absence_task_server.sh
```

### 3. **Configure Environment Variables**
Set these environment variables on your server:

```bash
# Required: Your API authentication token
export DAILY_ABSENCE_TOKEN="your_actual_jwt_token_here"

# Optional: Your server's API URL (defaults to localhost:8000)
export API_BASE_URL="http://your-server-domain.com:8000"

# Optional: Custom log directory (defaults to script_directory/logs)
export LOG_DIR="/var/log/daily-absence"
```

### 4. **Get Authentication Token**
To get a valid token:
1. Login to your API: `POST /assistant/login`
2. Copy the JWT token from the response
3. Set it as `DAILY_ABSENCE_TOKEN` environment variable

### 5. **Set Up Cron Job**
```bash
# Edit crontab
crontab -e

# Add this line to run at 11:59 PM daily
59 23 * * * /path/to/your/app/daily_absence_task_server.sh
```

## 🔧 Environment Variable Examples

### For Production Server:
```bash
export DAILY_ABSENCE_TOKEN="eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
export API_BASE_URL="https://api.yourschool.com"
export LOG_DIR="/var/log/daily-absence"
```

### For Development Server:
```bash
export DAILY_ABSENCE_TOKEN="your_dev_token_here"
export API_BASE_URL="http://dev-server:8000"
```

## 📁 Server Directory Structure
```
/your-app-directory/
├── daily_absence_task_server.sh    # The background task script
├── logs/                           # Log files (auto-created)
│   └── daily_absence.log
├── app/                           # Your FastAPI app
└── requirements.txt
```

## 🧪 Testing the Script
Before setting up cron, test manually:
```bash
# Set environment variables first
export DAILY_ABSENCE_TOKEN="your_token"
export API_BASE_URL="http://your-server:8000"

# Run the script
./daily_absence_task_server.sh

# Check logs
tail -f logs/daily_absence.log
```

## 🚨 Important Notes

1. **Token Expiration**: JWT tokens may expire. Monitor logs and renew tokens as needed.

2. **Server URL**: Change `API_BASE_URL` to match your production server:
   - Local: `http://localhost:8000`
   - Production: `https://api.yourschool.com`
   - Docker: `http://container-name:8000`

3. **Log Rotation**: Consider setting up log rotation for the log files.

4. **Monitoring**: Set up alerts for failed executions.

## 🔍 Troubleshooting

### Script fails with "Authentication token not configured!"
```bash
export DAILY_ABSENCE_TOKEN="your_actual_token"
```

### Script fails with "curl command not found!"
```bash
# Ubuntu/Debian
sudo apt-get install curl

# CentOS/RHEL
sudo yum install curl
```

### API connection fails
- Check if your FastAPI server is running
- Verify the `API_BASE_URL` is correct
- Check firewall/security group settings

### Logs not appearing
- Check if the script has write permissions to the log directory
- Verify the log directory exists and is writable

## 📊 Log Format
The script logs in this format:
```
[2024-08-31 23:59:01] Starting daily absence marking...
[2024-08-31 23:59:01] API URL: https://api.yourschool.com/admin/mark-daily-absences
[2024-08-31 23:59:02] HTTP Code: 200
[2024-08-31 23:59:02] Response: {"message":"Daily absences marked successfully","affected_students":15}
[2024-08-31 23:59:02] ✅ Daily absence marking completed successfully
----------------------------------------
```

## 🔄 Updating the Script
When you need to update:
1. Replace the script file on the server
2. Ensure it has executable permissions: `chmod +x script_name.sh`
3. The cron job will automatically use the updated script
