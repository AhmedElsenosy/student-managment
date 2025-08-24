from fastapi import APIRouter, HTTPException, Depends
from datetime import datetime, timedelta
from app.models.group import Group
from app.dependencies.auth import get_current_assistant
import pytz

router = APIRouter(prefix="/group-schedule", tags=["Group Schedule"])

@router.get("/active-groups")
async def get_active_groups(assistant=Depends(get_current_assistant)):
    """
    Get all groups that should be attending right now based on start_time and days only (±1 hour window)
    No level validation - purely based on schedule timing
    
    Returns:
        List of active groups with their details
    """
    try:
        # Get current time in Egypt timezone
        egypt_tz = pytz.timezone("Africa/Cairo")
        current_time = datetime.now(egypt_tz)
        current_day = current_time.strftime("%A")  # Gets day name like "Monday", "Tuesday", etc.
        
        print(f"🕒 Group detection - Current time: {current_time.strftime('%H:%M')} on {current_day}")
        
        # Get all groups
        all_groups = await Group.find().to_list()
        print(f"📋 Found {len(all_groups)} total groups in database")
        
        active_groups = []
        
        for group in all_groups:
            print(f"\n🔍 Checking group: {group.group_name} (Level {group.level})")
            print(f"  - Start time: {group.start_time}")
            print(f"  - Allowed days: {[day.value for day in group.days]}")
            
            # Check if today is in group's allowed days
            allowed_days = [day.value for day in group.days]
            if current_day not in allowed_days:
                print(f"  ❌ Day check failed: {current_day} not in {allowed_days}")
                continue
            
            print(f"  ✅ Day check passed: {current_day} in {allowed_days}")
            
            # Check if current time is within ±1 hour of group's start time
            try:
                group_start_time = datetime.strptime(group.start_time, "%H:%M").time()
            except Exception as e:
                print(f"  ❌ Invalid time format: {group.start_time} - {e}")
                continue  # Skip groups with invalid time format
            
            today = current_time.date()
            scheduled_start_time = egypt_tz.localize(datetime.combine(today, group_start_time))
            allowed_start = scheduled_start_time - timedelta(hours=1)
            allowed_end = scheduled_start_time + timedelta(hours=1)
            
            print(f"  - Scheduled start: {scheduled_start_time.strftime('%H:%M')}")
            print(f"  - Allowed window: {allowed_start.strftime('%H:%M')} - {allowed_end.strftime('%H:%M')}")
            print(f"  - Current time: {current_time.strftime('%H:%M')}")
            
            # Check if current time is within the allowed window
            if allowed_start <= current_time <= allowed_end:
                print(f"  ✅ TIME CHECK PASSED - Group is ACTIVE!")
                active_groups.append({
                    "group_id": str(group.id),
                    "group_name": group.group_name,
                    "level": group.level,
                    "start_time": group.start_time,
                    "allowed_days": allowed_days,
                    "student_count": len(group.students),
                    "scheduled_start_time": scheduled_start_time.isoformat(),
                    "allowed_window": {
                        "start": allowed_start.isoformat(),
                        "end": allowed_end.isoformat()
                    }
                })
            else:
                print(f"  ❌ Time check failed - Group is INACTIVE")
        
        print(f"\n🎯 RESULT: {len(active_groups)} active groups found")
        for group in active_groups:
            print(f"  - {group['group_name']} (Level {group['level']}) at {group['start_time']}")
        
        return {
            "success": True,
            "current_time": current_time.isoformat(),
            "current_day": current_day,
            "active_groups": active_groups,
            "active_group_count": len(active_groups),
            "detection_method": "start_time + days only (no level validation)"
        }
        
    except Exception as e:
        print(f"❌ Error in group detection: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error detecting active groups: {str(e)}")
