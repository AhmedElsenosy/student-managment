# Simple Server Deployment - Daily Absence Task

## ✅ **YES, IT WILL WORK AUTOMATICALLY AFTER DEPLOYMENT!**

Since you removed authentication and provided your domain, the script is fully ready.

## 📋 Copy This File to Your Server:
- `daily_absence_task_final.sh`

## 🚀 Run These 2 Commands on Your Server:

### 1. Make Script Executable:
```bash
chmod +x daily_absence_task_final.sh
```

### 2. Set Up Cron Job (11:59 PM Daily):
```bash
echo "59 23 * * * $(pwd)/daily_absence_task_final.sh" | crontab -
```

## 🎉 That's It!

The script will now:
- ✅ Run every day at 11:59 PM
- ✅ Call: `https://offline-sys-api.in-general.net/admin/mark-daily-absences`
- ✅ Create logs in: `logs/daily_absence.log`
- ✅ No authentication required
- ✅ Works from any directory

## 📊 Check Logs:
```bash
tail -f logs/daily_absence.log
```

## ⚡ Test Immediately (Optional):
```bash
./daily_absence_task_final.sh
```

---

**🔥 ZERO Configuration Required - Deploy and Forget!**
