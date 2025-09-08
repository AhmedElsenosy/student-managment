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

class AssistantDecisionRequest(BaseModel):
    decision: str  # 'approve' or 'reject'
    reason: str = None  # Optional reason for the decision

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
    🚀 OPTIMIZED: Uses database-level filtering and indexes for maximum performance
    
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
        
        # 🚀 BUILD OPTIMIZED DATABASE QUERY
        query_filter = {
            "attendance": {"$exists": True, "$ne": {}}
        }
        
        # Add level filter to database query (uses attendance_level_index)
        if level is not None:
            query_filter["level"] = level
        
        # Add name search filter to database query (uses attendance_name_index or name_text_index)
        if q:
            # Use regex for partial matching (optimized with indexes)
            name_pattern = {"$regex": q, "$options": "i"}
            query_filter["$or"] = [
                {"first_name": name_pattern},
                {"last_name": name_pattern}
            ]
        
        # Get group filter constraint if provided (uses groups_name_index)
        group_student_ids = None
        if group_name:
            group = await Group.find_one(Group.group_name == group_name)
            if group:
                # Add group filter to database query
                query_filter["_id"] = {"$in": group.students}
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
        
        # 🚀 EXECUTE OPTIMIZED DATABASE QUERY
        students_cursor = student_collection.find(query_filter)
        
        absent_students = []
        total_absent_records = 0
        
        # Pre-fetch groups for efficient lookups
        groups_by_student = {}
        all_groups = await Group.find_all().to_list()
        for group in all_groups:
            for student_id in group.students:
                groups_by_student[student_id] = group.group_name
        
        async for student in students_cursor:
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
                
                # Get student's group name from pre-fetched mapping
                group_name_value = groups_by_student.get(ObjectId(student["_id"]))
                
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
    🚀 OPTIMIZED: Uses database-level filtering and indexes for maximum performance
    
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
        
        # 🚀 BUILD OPTIMIZED DATABASE QUERY
        query_filter = {
            "attendance": {"$exists": True, "$ne": {}}
        }
        
        # Add level filter to database query (uses attendance_level_index)
        if level is not None:
            query_filter["level"] = level
        
        # Add name search filter to database query (uses attendance_name_index or name_text_index)
        if q:
            # Use regex for partial matching (optimized with indexes)
            name_pattern = {"$regex": q, "$options": "i"}
            query_filter["$or"] = [
                {"first_name": name_pattern},
                {"last_name": name_pattern}
            ]
        
        # Get group filter constraint if provided (uses groups_name_index)
        if group_name:
            group = await Group.find_one(Group.group_name == group_name)
            if group:
                # Add group filter to database query
                query_filter["_id"] = {"$in": group.students}
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
        
        # 🚀 EXECUTE OPTIMIZED DATABASE QUERY
        students_cursor = student_collection.find(query_filter)
        
        perfect_attendance_students = []
        total_present_records = 0
        
        # Pre-fetch groups for efficient lookups
        groups_by_student = {}
        all_groups = await Group.find_all().to_list()
        for group in all_groups:
            for student_id in group.students:
                groups_by_student[student_id] = group.group_name
        
        async for student in students_cursor:
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
                
                # Get student's group name from pre-fetched mapping
                group_name_value = groups_by_student.get(ObjectId(student["_id"]))
                
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


@router.get("/analytics")
async def get_attendance_analytics(assistant=Depends(get_current_assistant)):
    """
    Comprehensive attendance analytics showing:
    - Total student count
    - Overall present/absent counts and percentages (all time)
    - Breakdown by level with counts and percentages
    - Performance insights
    """
    try:
        # Get all students with attendance records
        students_cursor = student_collection.find({
            "attendance": {"$exists": True, "$ne": {}}
        })
        
        # Get total student count (all students in database)
        total_students_in_db = await student_collection.count_documents({})
        
        # Initialize counters
        total_attendance_records = 0
        total_present_records = 0
        total_absent_records = 0
        students_with_attendance = 0
        
        # Level-specific counters
        level_stats = {
            1: {"students": 0, "total_records": 0, "present": 0, "absent": 0},
            2: {"students": 0, "total_records": 0, "present": 0, "absent": 0},
            3: {"students": 0, "total_records": 0, "present": 0, "absent": 0}
        }
        
        # Process each student
        async for student in students_cursor:
            student_level = student.get("level")
            attendance_records = student.get("attendance", {})
            
            if attendance_records:
                students_with_attendance += 1
                
                # Count present and absent for this student
                student_present = 0
                student_absent = 0
                
                for date_str, status in attendance_records.items():
                    total_attendance_records += 1
                    if status is True:
                        student_present += 1
                        total_present_records += 1
                    elif status is False:
                        student_absent += 1
                        total_absent_records += 1
                
                # Update level statistics
                if student_level in level_stats:
                    level_stats[student_level]["students"] += 1
                    level_stats[student_level]["total_records"] += len(attendance_records)
                    level_stats[student_level]["present"] += student_present
                    level_stats[student_level]["absent"] += student_absent
        
        # Calculate overall percentages
        overall_present_percentage = (total_present_records / total_attendance_records * 100) if total_attendance_records > 0 else 0
        overall_absent_percentage = (total_absent_records / total_attendance_records * 100) if total_attendance_records > 0 else 0
        
        # Calculate level-specific percentages
        level_breakdown = []
        for level, stats in level_stats.items():
            level_total_records = stats["total_records"]
            level_present_percentage = (stats["present"] / level_total_records * 100) if level_total_records > 0 else 0
            level_absent_percentage = (stats["absent"] / level_total_records * 100) if level_total_records > 0 else 0
            
            level_breakdown.append({
                "level": level,
                "students_with_attendance": stats["students"],
                "total_attendance_records": level_total_records,
                "present_records": stats["present"],
                "absent_records": stats["absent"],
                "present_percentage": round(level_present_percentage, 2),
                "absent_percentage": round(level_absent_percentage, 2),
                "attendance_health": (
                    "Excellent" if level_present_percentage >= 95 else
                    "Very Good" if level_present_percentage >= 90 else
                    "Good" if level_present_percentage >= 85 else
                    "Fair" if level_present_percentage >= 80 else
                    "Poor" if level_present_percentage >= 70 else
                    "Critical"
                )
            })
        
        # Calculate additional insights
        avg_records_per_student = total_attendance_records / students_with_attendance if students_with_attendance > 0 else 0
        students_without_attendance = total_students_in_db - students_with_attendance
        
        # Find best and worst performing levels
        sorted_levels = sorted(level_breakdown, key=lambda x: x["present_percentage"], reverse=True)
        best_level = sorted_levels[0] if sorted_levels else None
        worst_level = sorted_levels[-1] if sorted_levels else None
        
        return {
            "success": True,
            "overall_summary": {
                "total_students_in_database": total_students_in_db,
                "students_with_attendance_records": students_with_attendance,
                "students_without_attendance_records": students_without_attendance,
                "total_attendance_records": total_attendance_records,
                "total_present_records": total_present_records,
                "total_absent_records": total_absent_records,
                "overall_present_percentage": round(overall_present_percentage, 2),
                "overall_absent_percentage": round(overall_absent_percentage, 2)
            },
            "level_breakdown": level_breakdown,
            "performance_insights": {
                "best_performing_level": {
                    "level": best_level["level"],
                    "present_percentage": best_level["present_percentage"],
                    "health_status": best_level["attendance_health"]
                } if best_level else None,
                "worst_performing_level": {
                    "level": worst_level["level"],
                    "present_percentage": worst_level["present_percentage"],
                    "health_status": worst_level["attendance_health"]
                } if worst_level else None,
                "overall_attendance_health": (
                    "Excellent" if overall_present_percentage >= 95 else
                    "Very Good" if overall_present_percentage >= 90 else
                    "Good" if overall_present_percentage >= 85 else
                    "Fair" if overall_present_percentage >= 80 else
                    "Poor" if overall_present_percentage >= 70 else
                    "Critical"
                ),
                "average_records_per_student": round(avg_records_per_student, 2),
                "attendance_coverage_percentage": round((students_with_attendance / total_students_in_db * 100), 2) if total_students_in_db > 0 else 0
            },
            "recommendations": {
                "focus_areas": [
                    f"Level {worst_level['level']} needs attention (only {worst_level['present_percentage']:.1f}% attendance)"
                    if worst_level and worst_level["present_percentage"] < 85 else None,
                    f"{students_without_attendance} students have no attendance records - consider initial attendance marking"
                    if students_without_attendance > 0 else None,
                    "Overall attendance is critical - immediate intervention needed"
                    if overall_present_percentage < 70 else None
                ],
                "positive_highlights": [
                    f"Level {best_level['level']} shows excellent attendance ({best_level['present_percentage']:.1f}%)"
                    if best_level and best_level["present_percentage"] >= 90 else None,
                    "Overall attendance is excellent - keep up the good work!"
                    if overall_present_percentage >= 95 else
                    "Overall attendance is good - minor improvements needed"
                    if overall_present_percentage >= 85 else None
                ]
            },
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error calculating attendance analytics: {str(e)}")


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
async def make_attendance_by_uid(
    uid: int, 
    assistant=Depends(get_current_assistant)
):
    """
    Make attendance for a student using their UID with smart validation and approval system
    
    🚀 NEW FEATURES:
    - Group-aware duplicate prevention
    - Assistant approval for non-group day attendance
    - Smart attendance assignment to missed group sessions
    - Prevents attendance abuse (attending group day + non-group day)
    
    Parameters:
    - uid: Student's unique identifier
    - assistant_decision: Optional - 'approve' or 'reject' for non-group day attendance
    """
    try:
        # Find the student by UID
        student = await StudentModel.find_one(StudentModel.uid == uid)
        if not student:
            raise HTTPException(status_code=404, detail="Student not found")
        
        # 🔍 FIND STUDENT'S GROUP (required for schedule validation)
        group = await Group.find(Group.students == student.id).first_or_none()
        if not group:
            raise HTTPException(status_code=404, detail="Student is not assigned to any group")
        
        # Get current timestamp and date in Egypt timezone
        egypt_tz = pytz.timezone("Africa/Cairo")
        now = datetime.now(egypt_tz)
        iso_timestamp = now.isoformat()
        today_date_key = now.strftime("%Y-%m-%d")
        current_day = now.strftime("%A")
        allowed_days = [day.value for day in group.days]
        
        # Initialize attendance if it doesn't exist
        if not hasattr(student, "attendance") or not isinstance(student.attendance, dict):
            student.attendance = {}
        
        # 🎯 MAIN LOGIC: Check if today is a group day or not
        is_group_day = current_day in allowed_days
        
        if is_group_day:
            # ✅ TODAY IS A GROUP DAY - Check time validation first
            
            # Check for duplicate attendance today
            if today_date_key in student.attendance:
                previous_status = student.attendance[today_date_key]
                previous_status_text = "Present" if previous_status else "Absent"
                raise HTTPException(
                    status_code=409,
                    detail=f"Student {student.first_name} {student.last_name} already marked as {previous_status_text} today ({today_date_key}). Cannot mark attendance twice on the same group session day."
                )
            
            # ⏰ TIME VALIDATION: Check if attendance time is within allowed window
            try:
                group_start_time_str = group.start_time
                group_start_time = datetime.strptime(group_start_time_str, "%H:%M").time()
            except Exception as e:
                raise HTTPException(status_code=500, detail=f"Invalid group start_time format: {e}")
            
            # Calculate allowed time window (1 hour before and after start time)
            today = now.date()
            scheduled_start_time = egypt_tz.localize(datetime.combine(today, group_start_time))
            allowed_start = scheduled_start_time - timedelta(hours=1)
            allowed_end = scheduled_start_time + timedelta(hours=1)
            
            is_within_time_window = allowed_start <= now <= allowed_end
            
            if is_within_time_window:
                # ✅ WITHIN TIME WINDOW - Record attendance directly
                student.attendance[today_date_key] = True
                await student.save()
                
                return {
                    "success": True,
                    "message": "Attendance recorded successfully (within time window)",
                    "uid": uid,
                    "student": f"{student.first_name} {student.last_name}",
                    "level": student.level,
                    "group": group.group_name,
                    "date": today_date_key,
                    "status": True,
                    "timestamp": iso_timestamp,
                    "day_of_week": current_day,
                    "attendance_type": "group_session_on_time",
                    "validation": {
                        "is_group_day": True,
                        "duplicate_check_passed": True,
                        "within_time_window": True,
                        "allowed_window": f"{allowed_start.strftime('%H:%M')} - {allowed_end.strftime('%H:%M')}",
                        "arrival_time": now.strftime('%H:%M')
                    }
                }
            else:
                # ⚠️ OUTSIDE TIME WINDOW - Require assistant decision
                return {
                    "success": False,
                    "requires_approval": True,
                    "message": f"Student {student.first_name} {student.last_name} wants to attend on {current_day} at {now.strftime('%H:%M')}. This is outside the allowed time window. Assistant decision required.",
                    "student_info": {
                        "uid": uid,
                        "name": f"{student.first_name} {student.last_name}",
                        "level": student.level,
                        "group": group.group_name
                    },
                    "violation_details": {
                        "attempted_day": current_day,
                        "attempted_time": now.strftime('%H:%M'),
                        "group_start_time": group_start_time_str,
                        "allowed_window": f"{allowed_start.strftime('%H:%M')} - {allowed_end.strftime('%H:%M')}",
                        "violation_type": "outside_time_window"
                    },
                    "instructions": "Use POST /attendance/assistant-decision/{uid} with decision parameter to approve/reject"
                }
        
        else:
            # ⚠️ TODAY IS NOT A GROUP DAY - Special validation needed
            
            # 🔍 FIND MOST RECENT GROUP DAY
            most_recent_group_day = None
            most_recent_group_date = None
            
            # Look back up to 14 days to find the most recent group day
            for days_back in range(1, 15):
                check_date = now - timedelta(days=days_back)
                check_day = check_date.strftime("%A")
                
                if check_day in allowed_days:
                    most_recent_group_day = check_day
                    most_recent_group_date = check_date.strftime("%Y-%m-%d")
                    break
            
            if not most_recent_group_date:
                raise HTTPException(
                    status_code=400,
                    detail="Cannot find recent group session day for validation"
                )
            
            # 🚫 CHECK: Did student attend the most recent group day?
            attended_recent_group = student.attendance.get(most_recent_group_date, None)
            
            if attended_recent_group is True:
                # Student already attended recent group day - REJECT without approval option
                raise HTTPException(
                    status_code=400,
                    detail=f"Student {student.first_name} {student.last_name} already attended {most_recent_group_day} ({most_recent_group_date}). Cannot mark attendance for non-group day when recent group session was already attended."
                )
            
            # 🎯 STUDENT MISSED RECENT GROUP DAY - Needs assistant approval
            
            # Return approval request - Assistant must use separate endpoint for decision
            return {
                "success": False,
                "requires_approval": True,
                "message": f"Student {student.first_name} {student.last_name} wants to attend on {current_day}. Student missed {most_recent_group_day} group session. Assistant decision required.",
                "student_info": {
                    "uid": uid,
                    "name": f"{student.first_name} {student.last_name}",
                    "level": student.level,
                    "group": group.group_name
                },
                "violation_details": {
                    "attempted_day": current_day,
                    "group_schedule": allowed_days,
                    "missed_group_day": most_recent_group_day,
                    "missed_group_date": most_recent_group_date,
                    "violation_type": "missed_recent_group_session"
                },
                "instructions": "Use POST /attendance/assistant-decision/{uid} with decision parameter to approve/reject"
            }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to mark attendance: {str(e)}")


@router.post("/assistant-decision/{uid}")
async def assistant_attendance_decision(
    uid: int,
    decision_data: AssistantDecisionRequest,
    assistant=Depends(get_current_assistant)
):
    """
    🎯 SEPARATE ASSISTANT DECISION ENDPOINT
    Handle assistant approval/rejection for non-group day attendance requests
    
    This endpoint implements the smart attendance assignment logic when assistant approves
    attendance for students who missed their group session day.
    
    Parameters:
    - uid: Student's unique identifier
    - decision_data: Contains decision ('approve' or 'reject') and optional reason
    """
    try:
        # Validate decision
        if decision_data.decision.lower() not in ["approve", "reject"]:
            raise HTTPException(
                status_code=400,
                detail="Invalid decision. Must be 'approve' or 'reject'"
            )
        
        # Find the student by UID
        student = await StudentModel.find_one(StudentModel.uid == uid)
        if not student:
            raise HTTPException(status_code=404, detail="Student not found")
        
        # Find student's group
        group = await Group.find(Group.students == student.id).first_or_none()
        if not group:
            raise HTTPException(status_code=404, detail="Student is not assigned to any group")
        
        # Get current timestamp and date
        egypt_tz = pytz.timezone("Africa/Cairo")
        now = datetime.now(egypt_tz)
        iso_timestamp = now.isoformat()
        today_date_key = now.strftime("%Y-%m-%d")
        current_day = now.strftime("%A")
        allowed_days = [day.value for day in group.days]
        
        # Initialize attendance if needed
        if not hasattr(student, "attendance") or not isinstance(student.attendance, dict):
            student.attendance = {}
        
        # Determine if today is a group day
        is_group_day = current_day in allowed_days
        
        # This endpoint handles two scenarios:
        # 1. Non-group days (missed recent group session)
        # 2. Group days with time violations (outside allowed time window)
        
        if decision_data.decision.lower() == "reject":
            # ❌ ASSISTANT REJECTED - No changes made
            return {
                "success": False,
                "message": "Attendance request rejected by assistant",
                "decision": "rejected",
                "reason": decision_data.reason or "No reason provided",
                "uid": uid,
                "student": f"{student.first_name} {student.last_name}",
                "level": student.level,
                "group": group.group_name,
                "attempted_date": today_date_key,
                "attempted_day": current_day,
                "attendance_recorded": False,
                "timestamp": iso_timestamp
            }
        
        elif decision_data.decision.lower() == "approve":
            # ✅ ASSISTANT APPROVED - Apply smart attendance logic
            
            target_date = None
            action_taken = None
            
            if is_group_day:
                # 🎯 GROUP DAY WITH TIME VIOLATION - Mark attendance for today
                # Check for duplicate attendance today
                if today_date_key in student.attendance:
                    previous_status = student.attendance[today_date_key]
                    previous_status_text = "Present" if previous_status else "Absent"
                    raise HTTPException(
                        status_code=409,
                        detail=f"Student {student.first_name} {student.last_name} already marked as {previous_status_text} today ({today_date_key}). Cannot mark attendance twice on the same group session day."
                    )
                
                # Mark attendance for today (group day with assistant approval)
                student.attendance[today_date_key] = True
                target_date = today_date_key
                action_taken = "group_day_time_violation_approved"
                
            else:
                # 🎯 NON-GROUP DAY - SMART ATTENDANCE ASSIGNMENT LOGIC
                
                # Priority 1: Find most recent absent day (false) in group schedule
                recent_absent_date = None
                for days_back in range(1, 30):  # Look back 30 days
                    check_date = now - timedelta(days=days_back)
                    check_day = check_date.strftime("%A")
                    check_date_key = check_date.strftime("%Y-%m-%d")
                    
                    if check_day in allowed_days:
                        attendance_status = student.attendance.get(check_date_key, None)
                        if attendance_status is False:  # Found absent day
                            recent_absent_date = check_date_key
                            break
                
                if recent_absent_date:
                    # Change most recent absent to present
                    student.attendance[recent_absent_date] = True
                    target_date = recent_absent_date
                    action_taken = "changed_absent_to_present"
                
                else:
                    # Priority 2: Find most recent missing group day
                    recent_missing_date = None
                    for days_back in range(1, 30):
                        check_date = now - timedelta(days=days_back)
                        check_day = check_date.strftime("%A")
                        check_date_key = check_date.strftime("%Y-%m-%d")
                        
                        if check_day in allowed_days and check_date_key not in student.attendance:
                            recent_missing_date = check_date_key
                            break
                    
                    if recent_missing_date:
                        # Mark most recent missing group day as present
                        student.attendance[recent_missing_date] = True
                        target_date = recent_missing_date
                        action_taken = "marked_missing_day_present"
                    
                    else:
                        # Priority 3: Find the most recent group day and mark as present
                        most_recent_group_date = None
                        for days_back in range(1, 30):
                            check_date = now - timedelta(days=days_back)
                            check_day = check_date.strftime("%A")
                            check_date_key = check_date.strftime("%Y-%m-%d")
                            
                            if check_day in allowed_days:
                                most_recent_group_date = check_date_key
                                break
                        
                        if most_recent_group_date:
                            # Override most recent group day to present
                            student.attendance[most_recent_group_date] = True
                            target_date = most_recent_group_date
                            action_taken = "marked_recent_group_day_present"
                        else:
                            raise HTTPException(
                                status_code=400,
                                detail="Cannot find any recent group session day to assign attendance"
                            )
            
            # Save the student with updated attendance
            await student.save()
            
            return {
                "success": True,
                "message": "Attendance request approved and recorded by assistant",
                "decision": "approved",
                "reason": decision_data.reason or "Assistant approved makeup attendance",
                "uid": uid,
                "student": f"{student.first_name} {student.last_name}",
                "level": student.level,
                "group": group.group_name,
                "attempted_date": today_date_key,
                "attempted_day": current_day,
                "recorded_date": target_date,
                "recorded_day": datetime.strptime(target_date, "%Y-%m-%d").strftime("%A"),
                "status": True,
                "timestamp": iso_timestamp,
                "attendance_type": "assistant_approved_makeup",
                "action_taken": action_taken,
                "assistant_approved": True
            }
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to process assistant decision: {str(e)}")


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
