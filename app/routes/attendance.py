from fastapi import APIRouter, HTTPException, Depends
from datetime import datetime, timedelta
from app.models.student import StudentModel
from app.models.group import Group
from pydantic import BaseModel
from dateutil.parser import isoparse
from bson import ObjectId
from app.models.py_object_id import PyObjectId
from app.database import student_collection
from app.dependencies.auth import get_current_assistant, TokenData
import pytz

router = APIRouter(prefix="/attendance", tags=["Attendance"])

class AttendanceRequest(BaseModel):
    uid: int
    timestamp: str  # ISO format string, potentially with +03:00
    assistant_approved: bool = False  # Optional parameter to bypass group schedule validation
    is_absent: bool = False  # Optional parameter to mark student as absent
    marked_by_system: bool = False  # Optional parameter to indicate system marked absent

@router.post("/")
async def auto_attendance(data: AttendanceRequest, assistant=Depends(get_current_assistant)):
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

    # Skip validations 4 and 5 if assistant approved OR if marking absent (system can mark absent anytime)
    if not data.assistant_approved and not data.is_absent:
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

    # Set attendance status based on whether it's absent or present
    attendance_status = False if data.is_absent else True
    student.attendance[date_key] = attendance_status
    await student.save()

    # Create appropriate message
    if data.is_absent:
        message = "Absent attendance recorded successfully"
        if data.marked_by_system:
            message += " (System marked - student did not attend)"
    else:
        message = "Present attendance recorded successfully"
        if data.assistant_approved:
            message += " (Assistant Approved - bypassed schedule validation)"
    
    return {
        "success": True,
        "message": message,
        "uid": data.uid,
        "student": f"{student.first_name} {student.last_name}",
        "group": group.group_name,
        "date": date_key,
        "status": attendance_status,
        "timestamp": local_timestamp.isoformat(),
        "is_absent": data.is_absent,
        "marked_by_system": data.marked_by_system,
        "assistant_approved": data.assistant_approved
    }

@router.get("/absent")
async def get_all_absent_students(
    page: int = 1, 
    limit: int = 10, 
    q: str = None,
    level: int = None,
    group_name: str = None,
    assistant=Depends(get_current_assistant)
):
    """
    Get all students who have absent records (attendance = False) and their absent dates
    
    Args:
        page: Page number (1-based, default: 1)
        limit: Number of students per page (default: 10)
        q: Optional search query to filter by student names (case-insensitive partial match)
        level: Optional filter by student level (1, 2, or 3)
        group_name: Optional filter by group name
    
    Returns:
        Dictionary containing paginated students with absent records and their specific absent dates
    """
    try:
        # Validate pagination parameters
        if page < 1:
            raise HTTPException(status_code=400, detail="Page number must be >= 1")
        if limit < 1:
            raise HTTPException(status_code=400, detail="Limit must be >= 1")
        
        # Find all students who have attendance records using direct MongoDB access
        students_cursor = student_collection.find({
            "attendance": {"$exists": True, "$ne": {}}
        })
        
        absent_students = []
        total_absent_records = 0
        
        # Get group filter constraint if provided
        group_student_ids = None
        if group_name:
            group = await Group.find_one(Group.group_name == group_name)
            if group:
                group_student_ids = set(str(student_id) for student_id in group.students)
            else:
                # Group not found, return empty result
                return {
                    "success": True,
                    "students": [],
                    "pagination": {
                        "current_page": page,
                        "limit": limit,
                        "total_pages": 0,
                        "total_students": 0,
                        "has_next": False,
                        "has_previous": page > 1
                    },
                    "summary": {
                        "total_students_with_absences": 0,
                        "total_absent_records": 0,
                        "most_absent_student": None,
                        "showing_students": 0
                    },
                    "filters_applied": {
                        "search_query": q,
                        "level_filter": level,
                        "group_filter": group_name
                    },
                    "message": f"Group '{group_name}' not found"
                }

        async for student in students_cursor:
            # Apply level filter
            if level is not None and student.get("level") != level:
                continue
                
            # Apply group filter
            if group_student_ids is not None and str(student["_id"]) not in group_student_ids:
                continue
            
            attendance_records = student.get("attendance", {})
            
            # Find all absent dates (where attendance = False)
            absent_dates = []
            for date_str, status in attendance_records.items():
                if status is False:  # Explicitly check for False (not just falsy)
                    try:
                        absent_dates.append({
                            "date": date_str,
                            "day_of_week": datetime.strptime(date_str, "%Y-%m-%d").strftime("%A")
                        })
                    except ValueError:
                        # Skip invalid date formats
                        continue
            
            # Only include students who have at least one absent record
            if absent_dates:
                # Sort absent dates by date (most recent first)
                absent_dates.sort(key=lambda x: x["date"], reverse=True)
                
                # Get student's group name
                group_name_value = None
                try:
                    student_obj = await StudentModel.find_one(StudentModel.id == PyObjectId(str(student["_id"])))
                    if student_obj:
                        group = await Group.find(Group.students == student_obj.id).first_or_none()
                        if group:
                            group_name_value = group.group_name
                except Exception:
                    # If group lookup fails, continue without group name
                    pass
                
                student_data = {
                    "student_info": {
                        "id": str(student["_id"]),
                        "student_id": student.get("student_id"),
                        "first_name": student.get("first_name"),
                        "last_name": student.get("last_name"),
                        "email": student.get("email"),
                        "level": student.get("level"),
                        "uid": student.get("uid"),
                        "group_name": group_name_value
                    },
                    "absent_dates": absent_dates,
                    "total_absent_days": len(absent_dates)
                }
                
                # Apply search filter
                if q:
                    first_name = student.get("first_name", "").lower()
                    last_name = student.get("last_name", "").lower()
                    full_name = f"{first_name} {last_name}".strip()
                    search_query = q.lower()
                    
                    # Check if search query matches any name component
                    if (search_query in first_name or 
                        search_query in last_name or 
                        search_query in full_name):
                        absent_students.append(student_data)
                        total_absent_records += len(absent_dates)
                else:
                    absent_students.append(student_data)
                    total_absent_records += len(absent_dates)
        
        # Sort students by number of absent days (descending), then by name
        absent_students.sort(key=lambda x: (-x["total_absent_days"], x["student_info"]["first_name"] or "", x["student_info"]["last_name"] or ""))
        
        # Calculate pagination
        total_students = len(absent_students)
        total_pages = (total_students + limit - 1) // limit  # Ceiling division
        start_index = (page - 1) * limit
        end_index = start_index + limit
        paginated_students = absent_students[start_index:end_index]
        
        return {
            "success": True,
            "students": paginated_students,
            "pagination": {
                "current_page": page,
                "limit": limit,
                "total_pages": total_pages,
                "total_students": total_students,
                "has_next": page < total_pages,
                "has_previous": page > 1
            },
            "summary": {
                "total_students_with_absences": total_students,
                "total_absent_records": total_absent_records,
                "most_absent_student": {
                    "name": f"{absent_students[0]['student_info']['first_name']} {absent_students[0]['student_info']['last_name']}",
                    "absent_days": absent_students[0]['total_absent_days']
                } if absent_students else None,
                "showing_students": len(paginated_students)
            },
            "filters_applied": {
                "search_query": q,
                "level_filter": level,
                "group_filter": group_name
            }
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error retrieving absent students: {str(e)}")


@router.get("/present")
async def get_all_present_students(
    page: int = 1, 
    limit: int = 10, 
    q: str = None,
    level: int = None,
    group_name: str = None,
    assistant=Depends(get_current_assistant)
):
    """
    Get all students who have only present attendance records (no absent records)
    Perfect attendance students - those who have never been marked absent
    
    Args:
        page: Page number (1-based, default: 1)
        limit: Number of students per page (default: 10)
        q: Optional search query to filter by student names (case-insensitive partial match)
        level: Optional filter by student level (1, 2, or 3)
        group_name: Optional filter by group name
    
    Returns:
        Dictionary containing paginated students with perfect attendance and their present dates
    """
    try:
        # Validate pagination parameters
        if page < 1:
            raise HTTPException(status_code=400, detail="Page number must be >= 1")
        if limit < 1:
            raise HTTPException(status_code=400, detail="Limit must be >= 1")
        
        # Find all students who have attendance records using direct MongoDB access
        students_cursor = student_collection.find({
            "attendance": {"$exists": True, "$ne": {}}
        })
        
        perfect_attendance_students = []
        total_present_records = 0
        
        # Get group filter constraint if provided
        group_student_ids = None
        if group_name:
            group = await Group.find_one(Group.group_name == group_name)
            if group:
                group_student_ids = set(str(student_id) for student_id in group.students)
            else:
                # Group not found, return empty result
                return {
                    "success": True,
                    "students": [],
                    "pagination": {
                        "current_page": page,
                        "limit": limit,
                        "total_pages": 0,
                        "total_students": 0,
                        "has_next": False,
                        "has_previous": page > 1
                    },
                    "summary": {
                        "total_students_with_perfect_attendance": 0,
                        "total_present_records": 0,
                        "most_present_student": None,
                        "average_present_days": 0,
                        "showing_students": 0
                    },
                    "filters_applied": {
                        "search_query": q,
                        "level_filter": level,
                        "group_filter": group_name
                    },
                    "message": f"Group '{group_name}' not found"
                }
        
        async for student in students_cursor:
            # Apply level filter
            if level is not None and student.get("level") != level:
                continue
                
            # Apply group filter
            if group_student_ids is not None and str(student["_id"]) not in group_student_ids:
                continue
            
            attendance_records = student.get("attendance", {})
            
            # Check if student has any absent records (False values)
            has_absent_records = any(status is False for status in attendance_records.values())
            
            # Only include students with NO absent records and at least one present record
            if not has_absent_records and attendance_records:
                # Get all present dates (where attendance = True)
                present_dates = []
                for date_str, status in attendance_records.items():
                    if status is True:  # Explicitly check for True
                        try:
                            present_dates.append({
                                "date": date_str,
                                "day_of_week": datetime.strptime(date_str, "%Y-%m-%d").strftime("%A")
                            })
                        except ValueError:
                            # Skip invalid date formats
                            continue
                
                # Sort present dates by date (most recent first)
                present_dates.sort(key=lambda x: x["date"], reverse=True)
                
                # Get student's group name
                group_name_value = None
                try:
                    student_obj = await StudentModel.find_one(StudentModel.id == PyObjectId(str(student["_id"])))
                    if student_obj:
                        group = await Group.find(Group.students == student_obj.id).first_or_none()
                        if group:
                            group_name_value = group.group_name
                except Exception:
                    # If group lookup fails, continue without group name
                    pass
                
                student_data = {
                    "student_info": {
                        "id": str(student["_id"]),
                        "student_id": student.get("student_id"),
                        "first_name": student.get("first_name"),
                        "last_name": student.get("last_name"),
                        "email": student.get("email"),
                        "level": student.get("level"),
                        "uid": student.get("uid"),
                        "group_name": group_name_value
                    },
                    "present_dates": present_dates,
                    "total_present_days": len(present_dates),
                    "perfect_attendance": True
                }
                
                # Apply search filter
                if q:
                    first_name = student.get("first_name", "").lower()
                    last_name = student.get("last_name", "").lower()
                    full_name = f"{first_name} {last_name}".strip()
                    search_query = q.lower()
                    
                    # Check if search query matches any name component
                    if (search_query in first_name or 
                        search_query in last_name or 
                        search_query in full_name):
                        perfect_attendance_students.append(student_data)
                        total_present_records += len(present_dates)
                else:
                    perfect_attendance_students.append(student_data)
                    total_present_records += len(present_dates)
        
        # Sort students by number of present days (descending), then by name
        perfect_attendance_students.sort(key=lambda x: (-x["total_present_days"], x["student_info"]["first_name"] or "", x["student_info"]["last_name"] or ""))
        
        # Calculate pagination
        total_students = len(perfect_attendance_students)
        total_pages = (total_students + limit - 1) // limit  # Ceiling division
        start_index = (page - 1) * limit
        end_index = start_index + limit
        paginated_students = perfect_attendance_students[start_index:end_index]
        
        return {
            "success": True,
            "students": paginated_students,
            "pagination": {
                "current_page": page,
                "limit": limit,
                "total_pages": total_pages,
                "total_students": total_students,
                "has_next": page < total_pages,
                "has_previous": page > 1
            },
            "summary": {
                "total_students_with_perfect_attendance": total_students,
                "total_present_records": total_present_records,
                "most_present_student": {
                    "name": f"{perfect_attendance_students[0]['student_info']['first_name']} {perfect_attendance_students[0]['student_info']['last_name']}",
                    "present_days": perfect_attendance_students[0]['total_present_days']
                } if perfect_attendance_students else None,
                "average_present_days": round(total_present_records / len(perfect_attendance_students), 2) if perfect_attendance_students else 0,
                "showing_students": len(paginated_students)
            },
            "filters_applied": {
                "search_query": q,
                "level_filter": level,
                "group_filter": group_name
            },
            "message": f"Found {total_students} student(s) with perfect attendance (no absent records), showing {len(paginated_students)} on this page"
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error retrieving perfect attendance students: {str(e)}")


@router.get("/absent/{student_id}")
async def get_student_absent_records(student_id: str, assistant=Depends(get_current_assistant)):
    """
    Get only the absent records (attendance = False) for a specific student
    
    Args:
        student_id: The ObjectId of the student (e.g., "688f6e20c4535772b8b81c26")
    
    Returns:
        Dictionary containing student info and only their absent dates
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
        
        # Filter only absent dates (where attendance = False)
        absent_dates = []
        for date_str, status in attendance_records.items():
            if status is False:  # Explicitly check for False (not just falsy)
                try:
                    absent_dates.append({
                        "date": date_str,
                        "status": status,
                        "day_of_week": datetime.strptime(date_str, "%Y-%m-%d").strftime("%A")
                    })
                except ValueError:
                    # Skip invalid date formats
                    continue
        
        # Sort by date (most recent first)
        absent_dates.sort(key=lambda x: x["date"], reverse=True)
        
        # Calculate statistics
        total_attendance_days = len(attendance_records)
        total_absent_days = len(absent_dates)
        absent_percentage = (total_absent_days / total_attendance_days * 100) if total_attendance_days > 0 else 0
        
        # Get student's group name
        group_name = None
        try:
            group = await Group.find(Group.students == student.id).first_or_none()
            if group:
                group_name = group.group_name
        except Exception:
            # If group lookup fails, continue without group name
            pass
        
        return {
            "success": True,
            "student": {
                "id": str(student.id),
                "student_id": student.student_id,
                "first_name": student.first_name,
                "last_name": student.last_name,
                "email": student.email,
                "level": student.level,
                "uid": student.uid,
                "group_name": group_name
            },
            "absent_records": {
                "dates": absent_dates,
                "statistics": {
                    "total_attendance_days": total_attendance_days,
                    "total_absent_days": total_absent_days,
                    "present_days": total_attendance_days - total_absent_days,
                    "absent_percentage": round(absent_percentage, 2)
                }
            },
            "message": f"Found {total_absent_days} absent day(s) out of {total_attendance_days} total attendance day(s)" if total_attendance_days > 0 else "No attendance records found for this student"
        }
        
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid ObjectId format")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@router.get("/{student_id}")
async def get_student_attendance(student_id: str, assistant=Depends(get_current_assistant)):
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
        
        # Get student's group name
        group_name = None
        try:
            group = await Group.find(Group.students == student.id).first_or_none()
            if group:
                group_name = group.group_name
        except Exception:
            # If group lookup fails, continue without group name
            pass
        
        return {
            "success": True,
            "student": {
                "id": str(student.id),
                "student_id": student.student_id,
                "first_name": student.first_name,
                "last_name": student.last_name,
                "email": student.email,
                "level": student.level,
                "uid": student.uid,
                "group_name": group_name
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
async def get_student_attendance_direct(student_id: str, assistant=Depends(get_current_assistant)):
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


@router.post("/make-attendance/{uid}")
async def make_attendance_by_uid(uid: int, assistant=Depends(get_current_assistant)):
    """
    Make attendance for a student using their UID (moved from fingerprint backend)
    This endpoint allows manual attendance marking by UID
    """
    try:
        # Find the student by UID
        student = await StudentModel.find_one(StudentModel.uid == uid)
        if not student:
            raise HTTPException(status_code=404, detail="Student not found")
        
        # Get current timestamp and date in Egypt timezone
        egypt_tz = pytz.timezone("Africa/Cairo")
        now = datetime.now(egypt_tz)
        iso_timestamp = now.isoformat()
        date_key = now.strftime("%Y-%m-%d")
        
        # Initialize attendance if it doesn't exist
        if not hasattr(student, "attendance") or not isinstance(student.attendance, dict):
            student.attendance = {}
        
        # Mark attendance as present with assistant approved (bypasses schedule validation)
        student.attendance[date_key] = True
        await student.save()
        
        # Get student's group name for response
        group = await Group.find(Group.students == student.id).first_or_none()
        group_name = group.group_name if group else "No Group"
        
        return {
            "success": True,
            "message": "Manual attendance recorded successfully",
            "uid": uid,
            "student": f"{student.first_name} {student.last_name}",
            "group": group_name,
            "date": date_key,
            "status": True,
            "timestamp": iso_timestamp,
            "is_manual": True,
            "assistant_approved": True
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to mark attendance: {str(e)}")


@router.post("/undo-last/{uid}")
async def undo_last_attendance(uid: int, assistant: TokenData = Depends(get_current_assistant)):
    """
    Undo the most recent attendance record for a student by their UID.
    Removes the latest attendance entry completely from the student's record.
    
    Args:
        uid: Student's unique identifier
        assistant: Current authenticated assistant
    
    Returns:
        Dictionary containing confirmation of undone attendance and updated statistics
    """
    try:
        # Find the student by UID
        student = await StudentModel.find_one(StudentModel.uid == uid)
        if not student:
            raise HTTPException(status_code=404, detail=f"Student not found with UID: {uid}")
        
        # Check if student has attendance records
        if not hasattr(student, "attendance") or not isinstance(student.attendance, dict):
            raise HTTPException(status_code=400, detail="Student has no attendance records to undo")
        
        attendance_records = student.attendance
        
        # Check if attendance dictionary is empty
        if not attendance_records:
            raise HTTPException(status_code=400, detail="Student has no attendance records to undo")
        
        # Find the most recent attendance date
        # Convert date strings to datetime objects for proper sorting
        valid_dates = []
        for date_str in attendance_records.keys():
            try:
                date_obj = datetime.strptime(date_str, "%Y-%m-%d")
                valid_dates.append((date_str, date_obj))
            except ValueError:
                # Skip invalid date formats
                continue
        
        if not valid_dates:
            raise HTTPException(status_code=400, detail="No valid attendance dates found to undo")
        
        # Sort by date (most recent first) and get the latest
        valid_dates.sort(key=lambda x: x[1], reverse=True)
        last_date_str, last_date_obj = valid_dates[0]
        
        # Get the previous status before removal
        previous_status = attendance_records[last_date_str]
        previous_status_text = "Present" if previous_status else "Absent"
        
        # Remove the last attendance record
        del student.attendance[last_date_str]
        
        # Save the updated student record
        await student.save()
        
        # Calculate updated statistics
        remaining_records = student.attendance
        total_days = len(remaining_records)
        present_days = sum(1 for status in remaining_records.values() if status)
        absent_days = total_days - present_days
        attendance_percentage = (present_days / total_days * 100) if total_days > 0 else 0
        
        # Get student's group information
        group = await Group.find(Group.students == student.id).first_or_none()
        group_name = group.group_name if group else "No Group"
        
        # Get current timestamp in Egypt timezone
        egypt_tz = pytz.timezone("Africa/Cairo")
        now = datetime.now(egypt_tz)
        
        # Get day of week for the undone date
        day_of_week = last_date_obj.strftime("%A")
        
        return {
            "success": True,
            "message": "Last attendance successfully undone",
            "student": {
                "uid": uid,
                "student_id": student.student_id,
                "name": f"{student.first_name} {student.last_name}",
                "first_name": student.first_name,
                "last_name": student.last_name,
                "level": student.level,
                "group": group_name
            },
            "undone_record": {
                "date": last_date_str,
                "previous_status": previous_status,
                "previous_status_text": previous_status_text,
                "day_of_week": day_of_week
            },
            "updated_statistics": {
                "total_days": total_days,
                "present_days": present_days,
                "absent_days": absent_days,
                "attendance_percentage": round(attendance_percentage, 2)
            },
            "operation_info": {
                "performed_by": assistant.username if hasattr(assistant, 'username') else "Assistant",
                "timestamp": now.isoformat(),
                "operation": "undo_last_attendance"
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to undo last attendance: {str(e)}")
