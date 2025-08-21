from fastapi import APIRouter, HTTPException
from datetime import datetime, timedelta
from app.models.student import StudentModel
from app.models.group import Group
from pydantic import BaseModel
from dateutil.parser import isoparse
from bson import ObjectId
from app.models.py_object_id import PyObjectId
from app.database import student_collection
import pytz

router = APIRouter(prefix="/attendance", tags=["Attendance"])

class AttendanceRequest(BaseModel):
    uid: int
    timestamp: str  # ISO format string, potentially with +03:00
    assistant_approved: bool = False  # Optional parameter to bypass group schedule validation

@router.post("/")
async def auto_attendance(data: AttendanceRequest):
    try:
        # Parse timestamp (aware or naive)
        aware_timestamp = isoparse(data.timestamp)
        egypt_tz = pytz.timezone("Africa/Cairo")
        # Ensure timestamp is in Egypt time
        local_timestamp = aware_timestamp.astimezone(egypt_tz)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid input format: {e}")

    # 1. Check if student exists
    student = await StudentModel.find_one(StudentModel.uid == data.uid)
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")

    # 2. Check if student belongs to a group
    group = await Group.find(Group.students == student.id).first_or_none()
    if not group:
        raise HTTPException(status_code=404, detail="Student is not assigned to any group")

    # 3. Check if student's level matches group's level
    if student.level != group.level:
        raise HTTPException(
            status_code=400, 
            detail=f"Student level ({student.level}) does not match group level ({group.level})"
        )

    # Skip validations 4 and 5 if assistant approved
    if not data.assistant_approved:
        # 4. Check if current day is in group's allowed days
        current_day = local_timestamp.strftime("%A")  # Gets day name like "Monday", "Tuesday", etc.
        allowed_days = [day.value for day in group.days]  # Convert enum to string values
        if current_day not in allowed_days:
            raise HTTPException(
                status_code=400,
                detail=f"Attendance not allowed on {current_day}. Group schedule: {', '.join(allowed_days)}"
            )

        # 5. Check if attendance time is within allowed window
        try:
            group_start_time_str = group.start_time
            group_start_time = datetime.strptime(group_start_time_str, "%H:%M").time()
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Invalid group start_time format: {e}")

        today = local_timestamp.date()
        scheduled_start_time = egypt_tz.localize(datetime.combine(today, group_start_time))
        allowed_start = scheduled_start_time - timedelta(hours=1)
        allowed_end = scheduled_start_time + timedelta(hours=1)

        is_on_time = allowed_start <= local_timestamp <= allowed_end
        if not is_on_time:
            raise HTTPException(
                status_code=400,
                detail=f"Attendance time ({local_timestamp.strftime('%H:%M')}) is outside allowed window ({allowed_start.strftime('%H:%M')} - {allowed_end.strftime('%H:%M')})"
            )

    # All validations passed - record attendance
    if not hasattr(student, "attendance") or not isinstance(student.attendance, dict):
        student.attendance = {}

    # Use date format as key (YYYY-MM-DD)
    date_key = local_timestamp.strftime("%Y-%m-%d")

    student.attendance[date_key] = True  # Always True if all validations pass
    await student.save()

    message = "Attendance recorded successfully"
    if data.assistant_approved:
        message += " (Assistant Approved - bypassed schedule validation)"
    
    return {
        "success": True,
        "message": message,
        "uid": data.uid,
        "student": f"{student.first_name} {student.last_name}",
        "group": group.group_name,
        "date": date_key,
        "status": True,
        "timestamp": local_timestamp.isoformat(),
        "assistant_approved": data.assistant_approved
    }

@router.get("/{student_id}")
async def get_student_attendance(student_id: str):
    """
    Get all attendance records for a student by their MongoDB _id (ObjectId)
    
    Args:
        student_id: The ObjectId of the student (e.g., "688f6e20c4535772b8b81c26")
    
    Returns:
        Dictionary containing student info and all attendance records
    """
    try:
        # Validate ObjectId format first
        if not ObjectId.is_valid(student_id):
            raise HTTPException(status_code=400, detail=f"Invalid ObjectId format: {student_id}")
        
        # Convert string to PyObjectId for Beanie compatibility
        try:
            py_object_id = PyObjectId(student_id)
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Error converting ObjectId: {str(e)}")
        
        # Find student by ObjectId using Beanie ORM
        student = await StudentModel.find_one(StudentModel.id == py_object_id)
        if not student:
            raise HTTPException(status_code=404, detail=f"Student not found with ID: {student_id}")
        
        # Get attendance records
        attendance_records = student.attendance if hasattr(student, 'attendance') and student.attendance else {}
        
        # Convert attendance dict to a more structured format
        attendance_list = []
        for date_str, status in attendance_records.items():
            attendance_list.append({
                "date": date_str,
                "status": status,
                "day_of_week": datetime.strptime(date_str, "%Y-%m-%d").strftime("%A")
            })
        
        # Sort by date (most recent first)
        attendance_list.sort(key=lambda x: x["date"], reverse=True)
        
        # Calculate attendance statistics
        total_days = len(attendance_list)
        present_days = sum(1 for record in attendance_list if record["status"])
        attendance_percentage = (present_days / total_days * 100) if total_days > 0 else 0
        
        return {
            "success": True,
            "student": {
                "id": str(student.id),
                "student_id": student.student_id,
                "first_name": student.first_name,
                "last_name": student.last_name,
                "email": student.email,
                "level": student.level,
                "uid": student.uid
            },
            "attendance": {
                "records": attendance_list,
                "statistics": {
                    "total_days": total_days,
                    "present_days": present_days,
                    "absent_days": total_days - present_days,
                    "attendance_percentage": round(attendance_percentage, 2)
                }
            }
        }
        
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid ObjectId format")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@router.get("/direct/{student_id}")
async def get_student_attendance_direct(student_id: str):
    """
    Alternative endpoint using direct MongoDB access (bypasses Beanie ORM)
    Get all attendance records for a student by their MongoDB _id
    
    Args:
        student_id: The ObjectId string (e.g., "688f6e20c4535772b8b81c26")
    """
    try:
        # Convert to ObjectId
        obj_id = ObjectId(student_id)
        
        # Find student using direct MongoDB query
        student = await student_collection.find_one({"_id": obj_id})
        if not student:
            raise HTTPException(status_code=404, detail=f"Student not found with ID: {student_id}")
        
        # Extract attendance records
        attendance_records = student.get("attendance", {})
        
        # Format attendance records
        attendance_list = []
        for date_str, status in attendance_records.items():
            try:
                attendance_list.append({
                    "date": date_str,
                    "status": status,
                    "day_of_week": datetime.strptime(date_str, "%Y-%m-%d").strftime("%A")
                })
            except ValueError:
                # Skip invalid date formats
                continue
        
        # Sort by date (most recent first)
        attendance_list.sort(key=lambda x: x["date"], reverse=True)
        
        # Calculate statistics
        total_days = len(attendance_list)
        present_days = sum(1 for record in attendance_list if record["status"])
        attendance_percentage = (present_days / total_days * 100) if total_days > 0 else 0
        
        return {
            "success": True,
            "student": {
                "id": str(student["_id"]),
                "student_id": student.get("student_id"),
                "first_name": student.get("first_name"),
                "last_name": student.get("last_name"),
                "email": student.get("email"),
                "level": student.get("level"),
                "uid": student.get("uid")
            },
            "attendance": {
                "records": attendance_list,
                "statistics": {
                    "total_days": total_days,
                    "present_days": present_days,
                    "absent_days": total_days - present_days,
                    "attendance_percentage": round(attendance_percentage, 2)
                }
            }
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error: {str(e)}")
