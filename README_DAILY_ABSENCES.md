# Daily Absence Marking System

This system automatically marks students as absent if they don't attend on their scheduled group days.

## How It Works

1. **Daily Schedule**: Runs every day at 11:59 PM Cairo time
2. **Logic**: 
   - Checks all groups in the database
   - For each group, determines if today is a scheduled day (based on the group's `days` field)
   - If today IS a scheduled day for the group → marks students as absent if they have no attendance record
   - If today IS NOT a scheduled day for the group → does nothing (skips the group)
3. **Attendance Format**: Stores attendance as `"2025-08-30": false` for absent students

## Files Created

1. **API Endpoint**: `/admin/mark-daily-absences` in `src/app/routes/admin.py`
2. **Shell Script**: `/home/ahmed/Desktop/teacher/venv/src/daily_absence_task.sh`
3. **Cron Job**: Runs daily at 23:59 (11:59 PM)
4. **Log File**: `/home/ahmed/Desktop/teacher/venv/src/logs/daily_absence.log`

## Setup Instructions

### Step 1: Get Authentication Token

You need to get a valid authentication token and update the shell script:

1. Login to get a token:
```bash
curl -X POST "http://localhost:8000/assistant/login" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=YOUR_USERNAME&password=YOUR_PASSWORD"
```

2. Copy the `access_token` from the response

3. Edit the shell script:
```bash
nano /home/ahmed/Desktop/teacher/venv/src/daily_absence_task.sh
```

4. Replace `YOUR_TOKEN_HERE` with the actual token

### Step 2: Test the System

1. **Test the API endpoint manually**:
```bash
curl -X POST "http://localhost:8000/admin/test-absence-marking?test_date=2025-08-30" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_ACTUAL_TOKEN"
```

2. **Test the shell script**:
```bash
/home/ahmed/Desktop/teacher/venv/src/daily_absence_task.sh
```

3. **Check the log file**:
```bash
cat /home/ahmed/Desktop/teacher/venv/src/logs/daily_absence.log
```

## API Endpoints

### 1. Production Endpoint
- **URL**: `POST /admin/mark-daily-absences`
- **Purpose**: Mark absences for today (Cairo time)
- **Authentication**: Required (Bearer token)

### 2. Test Endpoint
- **URL**: `POST /admin/test-absence-marking?test_date=YYYY-MM-DD`
- **Purpose**: Test absence marking for a specific date
- **Authentication**: Required (Bearer token)
- **Example**: `/admin/test-absence-marking?test_date=2025-08-30`

## Cron Job

The cron job is set to run at 23:59 (11:59 PM) every day:
```
59 23 * * * /home/ahmed/Desktop/teacher/venv/src/daily_absence_task.sh
```

### View current cron jobs:
```bash
crontab -l
```

### Edit cron jobs:
```bash
crontab -e
```

## Monitoring

### Check if cron service is running:
```bash
sudo systemctl status cron
```

### View cron logs:
```bash
sudo journalctl -u cron
```

### View application logs:
```bash
tail -f /home/ahmed/Desktop/teacher/venv/src/logs/daily_absence.log
```

## Troubleshooting

1. **Token expires**: Update the token in the shell script
2. **Server not running**: Ensure FastAPI server is running on localhost:8000
3. **Permissions**: Ensure the shell script is executable (`chmod +x`)
4. **Timezone**: The system uses Cairo timezone (Africa/Cairo)

## Example Response

Success response from the API:
```json
{
  "success": true,
  "date_processed": "2025-08-30",
  "weekday": "Saturday",
  "total_groups_processed": 2,
  "total_students_marked_absent": 5,
  "group_details": [
    {
      "group_name": "Group A",
      "students_in_group": 10,
      "students_marked_absent": 3
    }
  ],
  "message": "Successfully processed absences for 2025-08-30"
}
```

## Important Notes

- Only students in groups that are scheduled for today will be marked absent
- Students who already have attendance records (present or absent) will be skipped
- The system uses the group's `days` field to determine scheduled days
- All times are in Cairo timezone (Africa/Cairo)
