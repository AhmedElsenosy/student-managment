from fastapi import APIRouter, Depends, HTTPException
from datetime import datetime, date
from typing import Dict, List
import pytz
from app.models.group import Group, DayOfWeek
from app.models.student import StudentModel
from app.dependencies.auth import get_current_assistant
from beanie.operators import In

router = APIRouter(prefix="/admin", tags=["Admin"])

# Map Python weekday to DayOfWeek enum
# Python: Monday=0, Tuesday=1, ..., Sunday=6
# We need to map this to our DayOfWeek enum
WEEKDAY_MAPPING = {
    0: DayOfWeek.monday,
    1: DayOfWeek.tuesday, 
    2: DayOfWeek.wednesday,
    3: DayOfWeek.thursday,
    4: DayOfWeek.friday,
    5: DayOfWeek.saturday,
    6: DayOfWeek.sunday
}

@router.post("/mark-daily-absences")
async def mark_daily_absences(assistant=Depends(get_current_assistant)):
    """
    Background task endpoint to mark students as absent if they didn't attend
    on a day when their group was scheduled to meet.
    
    This should be called daily at 11:59 PM Cairo time via cron job.
    """
    try:
        # Get current date in Cairo timezone
        cairo_tz = pytz.timezone('Africa/Cairo')
        today_cairo = datetime.now(cairo_tz).date()
        today_str = today_cairo.strftime("%Y-%m-%d")
        
        # Get current weekday (Monday=0, Sunday=6)
        current_weekday = today_cairo.weekday()
        current_day_enum = WEEKDAY_MAPPING[current_weekday]
        
        print(f"Processing absences for {today_str} ({current_day_enum.value})")
        
        # Get all groups
        all_groups = await Group.find_all().to_list()
        
        processed_groups = 0
        total_students_marked_absent = 0
        group_results = []
        
        for group in all_groups:
            # Check if today is a scheduled day for this group
            if current_day_enum not in group.days:
                print(f"Group {group.group_name}: Today ({current_day_enum.value}) is not a scheduled day. Skipping.")
                continue
            
            print(f"Group {group.group_name}: Today is a scheduled day. Checking attendance...")
            processed_groups += 1
            
            # Get all students in this group
            if not group.students:
                print(f"Group {group.group_name}: No students in group")
                continue
                
            group_students = await StudentModel.find(In(StudentModel.id, group.students)).to_list()
            
            students_marked_absent_in_group = 0
            
            for student in group_students:
                # Check if student already has attendance record for today
                if today_str in student.attendance:
                    # Student already has attendance record (present or absent)
                    status = "present" if student.attendance[today_str] else "already absent"
                    print(f"Student {student.first_name} {student.last_name}: {status}")
                    continue
                
                # Student has no attendance record for today, mark as absent
                if not student.attendance:
                    student.attendance = {}
                
                student.attendance[today_str] = False
                await student.save()
                
                students_marked_absent_in_group += 1
                total_students_marked_absent += 1
                print(f"Student {student.first_name} {student.last_name}: Marked absent")
            
            group_results.append({
                "group_name": group.group_name,
                "students_in_group": len(group_students),
                "students_marked_absent": students_marked_absent_in_group
            })
        
        return {
            "success": True,
            "date_processed": today_str,
            "weekday": current_day_enum.value,
            "total_groups_processed": processed_groups,
            "total_students_marked_absent": total_students_marked_absent,
            "group_details": group_results,
            "message": f"Successfully processed absences for {today_str}"
        }
        
    except Exception as e:
        print(f"Error in mark_daily_absences: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error processing daily absences: {str(e)}")


@router.post("/test-absence-marking")
async def test_absence_marking(
    test_date: str = "2025-08-30",
    assistant=Depends(get_current_assistant)
):
    """
    Test endpoint to manually test absence marking for a specific date
    Format: YYYY-MM-DD
    """
    try:
        # Parse the test date
        test_date_obj = datetime.strptime(test_date, "%Y-%m-%d").date()
        test_date_str = test_date_obj.strftime("%Y-%m-%d")
        
        # Get weekday for test date
        test_weekday = test_date_obj.weekday()
        test_day_enum = WEEKDAY_MAPPING[test_weekday]
        
        print(f"Testing absences for {test_date_str} ({test_day_enum.value})")
        
        # Get all groups
        all_groups = await Group.find_all().to_list()
        
        processed_groups = 0
        total_students_marked_absent = 0
        group_results = []
        
        for group in all_groups:
            # Check if test date is a scheduled day for this group
            if test_day_enum not in group.days:
                continue
            
            processed_groups += 1
            
            # Get all students in this group
            if not group.students:
                continue
                
            group_students = await StudentModel.find(In(StudentModel.id, group.students)).to_list()
            
            students_marked_absent_in_group = 0
            
            for student in group_students:
                # Check if student already has attendance record for test date
                if test_date_str in student.attendance:
                    continue
                
                # Student has no attendance record for test date, mark as absent
                if not student.attendance:
                    student.attendance = {}
                
                student.attendance[test_date_str] = False
                await student.save()
                
                students_marked_absent_in_group += 1
                total_students_marked_absent += 1
            
            group_results.append({
                "group_name": group.group_name,
                "scheduled_days": [day.value for day in group.days],
                "students_in_group": len(group_students),
                "students_marked_absent": students_marked_absent_in_group
            })
        
        return {
            "success": True,
            "test_date": test_date_str,
            "weekday": test_day_enum.value,
            "total_groups_processed": processed_groups,
            "total_students_marked_absent": total_students_marked_absent,
            "group_details": group_results,
            "message": f"Test completed for {test_date_str}"
        }
        
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD")
    except Exception as e:
        print(f"Error in test_absence_marking: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error testing absences: {str(e)}")
