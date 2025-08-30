from fastapi import APIRouter, HTTPException, status, Depends, Query, Request
from app.database import db
from app.schemas.student import StudentCreate, StudentOut, StudentUpdate, StudentBase, PaginatedStudentsResponse
from app.models.student import StudentModel
from app.models.blacklist import BlacklistStudent
from app.routes.archive import archive_unpaid_students, move_student_to_archive
from app.schemas.archived_student import ArchiveRequest
from app.dependencies.auth import get_current_assistant
from bson import ObjectId
from datetime import datetime, date
from typing import List, Optional
from app.utils.fingerprint import enroll_fingerprint
import subprocess
from app.utils.id_generator import get_next_sequence
from app.models.counter import Counter
from app.models.group import Group
from app.models.booksale import BookSale
from app.models.monthsale import MonthlySale
import httpx
import os
from dotenv import load_dotenv
# For Excel processing
import pandas as pd
from fastapi import UploadFile, File
from app.schemas.excel_upload import ExcelUploadResponse, StudentCreationResult
from typing import Any, Dict


load_dotenv()
HOST_REMOTE_URL = os.getenv("HOST_REMOTE_URL")

# ✅ Apply authentication to all routes in this router
router = APIRouter(
    prefix="/students",
    tags=["Students"],
    dependencies=[Depends(get_current_assistant)]
)

students_collection = db["students"]
counters_collection = db["counters"]

# Utility to update students subscription status based on current month
async def update_students_subscription_status():
    # Get the current month in YYYY-MM format
    current_month = datetime.utcnow().strftime("%Y-%m")

    # Get all students
    students = await StudentModel.find_all().to_list()
    for student in students:
        # Check if the student has a monthsale in the current month
        current_month_sales = student.subscription.get("monthsales", {}).get(current_month, None)
        if current_month_sales is not None:
            student.is_subscription = True
        else:
            student.is_subscription = False

        # Update student if subscription status changed
        await student.save()

# Utility to generate the next student_id
async def get_next_student_id():
    counter = await Counter.find_one(Counter.name == "student_id")
    if not counter:
        counter = Counter(name="student_id", sequence_value=9999)  # So first will be 10000
        await counter.insert()
    counter.sequence_value += 1
    await counter.save()
    return counter.sequence_value

@router.get("/next-ids")
async def get_next_ids():
    """
    Get the next available student ID and UID without incrementing the counter.
    The counter will only be incremented when the student is actually created.
    """
    counter = await Counter.find_one(Counter.name == "student_id")
    next_id = counter.sequence_value + 1 if counter else 10000
    return {"student_id": next_id, "uid": next_id}


@router.post("/", response_model=StudentOut)
async def create_student(student: StudentCreate, request: Request = None):
    student_data = student.dict()
    
    # 🚫 PREVENT CIRCULAR SYNC: Check if request is coming from Fingerprint Backend
    is_from_fingerprint_backend = False
    if request:
        # Check if request has fingerprint_template data (indicates it's from Fingerprint Backend)
        if hasattr(student, 'fingerprint_template') and student.fingerprint_template:
            is_from_fingerprint_backend = True
            print(f"🔄 Detected request from Fingerprint Backend - skipping sync back to avoid duplicate")
        
        # Also check User-Agent or other headers that might indicate source
        user_agent = request.headers.get("user-agent", "")
        if "python-httpx" in user_agent.lower():
            is_from_fingerprint_backend = True
            print(f"🔄 Detected httpx request (likely from Fingerprint Backend) - skipping sync back to avoid duplicate")

    # Check if student exists in blacklist with same phone number
    blacklisted_by_phone = await BlacklistStudent.find_one(
        BlacklistStudent.phone_number == student_data["phone_number"]
    )
    
    # Check if student exists in blacklist with same first_name and last_name
    blacklisted_by_name = await BlacklistStudent.find_one(
        BlacklistStudent.first_name == student_data["first_name"],
        BlacklistStudent.last_name == student_data["last_name"]
    )
    
    if blacklisted_by_phone:
        raise HTTPException(
            status_code=400, 
            detail=f"Cannot create student. A student with the same phone number ({student_data['phone_number']}) exists in the blacklist."
        )
    
    if blacklisted_by_name:
        raise HTTPException(
            status_code=400, 
            detail=f"Cannot create student. A student with the same name ({student_data['first_name']} {student_data['last_name']}) exists in the blacklist."
        )

    next_id = await get_next_student_id()
    student_data["student_id"] = next_id
    student_data["uid"] = next_id

    # Convert birth_date to datetime
    if isinstance(student_data["birth_date"], date):
        student_data["birth_date"] = datetime.combine(student_data["birth_date"], datetime.min.time())

    # Convert enums
    student_data["gender"] = getattr(student_data["gender"], "value", student_data["gender"])
    student_data["level"] = getattr(student_data["level"], "value", student_data["level"])

    # Extra metadata
    student_data["created_at"] = datetime.utcnow()
    student_data["updated_at"] = None
    student_data["exams"] = []

    # Insert into Main Backend DB
    result = await students_collection.insert_one(student_data)
    student_data["id"] = str(result.inserted_id)
    
    # 🚀 SYNC TO FINGERPRINT BACKEND (only if NOT from Fingerprint Backend)
    if not is_from_fingerprint_backend:
        try:
            print(f"🔄 Syncing student {student_data['first_name']} {student_data['last_name']} to Fingerprint Backend...")
            
            # Get auth token if available
            token = None
            if request:
                token = request.headers.get("authorization")
            headers = {"Authorization": token} if token else {}
            
            # Prepare data for Fingerprint Backend
            sync_data = {
                "uid": student_data["uid"],
                "student_id": str(student_data["student_id"]),
                "first_name": student_data["first_name"],
                "last_name": student_data["last_name"],
                "email": student_data.get("email"),
                "phone_number": student_data["phone_number"],
                "guardian_number": student_data["guardian_number"],
                "birth_date": student_data.get("birth_date").isoformat() if student_data.get("birth_date") else None,
                "national_id": student_data.get("national_id"),
                "gender": student_data["gender"],
                "level": student_data["level"],
                "school_name": student_data.get("school_name"),
                "is_subscription": True,
                "fingerprint_template": None  # No fingerprint for this creation method
            }
            
            async with httpx.AsyncClient(timeout=10) as client:
                response = await client.post(
                    f"{HOST_REMOTE_URL}/students/sync-from-main",
                    json=sync_data,
                    headers=headers
                )
                
                if response.status_code == 200:
                    print(f"✅ Student {student_data['first_name']} {student_data['last_name']} successfully synced to Fingerprint Backend")
                else:
                    print(f"⚠️ Failed to sync student to Fingerprint Backend (status {response.status_code}): {response.text}")
                    # Don't fail the creation, just log the sync failure
                    
        except Exception as e:
            print(f"⚠️ Error syncing student to Fingerprint Backend: {str(e)}")
            # Don't fail the creation, just log the sync failure
    else:
        print(f"🚫 Skipping sync to Fingerprint Backend to prevent circular loop")

    return StudentOut(**student_data)



@router.get("/search", response_model=List[StudentOut])
async def search_students(
    q: str = Query(..., description="Search query for student name, phone number, or student ID"),
    level: Optional[int] = Query(None, ge=1, le=3, description="Filter by student level (1, 2, or 3)"),
    group: Optional[str] = Query(None, description="Filter by group name")
):
    """
    Search for students by name, phone number, or student ID with optional level and group filtering.
    Supports partial matching and case-insensitive search.
    Returns all matching results without pagination.
    
    Args:
        q: Search query (name, phone, or student ID)
        level: Optional filter by student level (1, 2, or 3)
        group: Optional filter by group name
    """
    await update_students_subscription_status()
    await archive_unpaid_students()
    
    # Build search query with improved Arabic name matching
    # Create word-boundary aware regex pattern for Arabic names
    # This will match the query as a separate word or at word boundaries
    word_boundary_pattern = f"(^|\\s){q}(\\s|$)"
    
    search_criteria = [
        # Search by first name - exact word match (case-insensitive)
        {"first_name": {"$regex": word_boundary_pattern, "$options": "i"}},
        # Search by last name - exact word match (case-insensitive)
        {"last_name": {"$regex": word_boundary_pattern, "$options": "i"}},
        # Search by full name - exact word match (case-insensitive)
        {"$expr": {
            "$regexMatch": {
                "input": {"$concat": ["$first_name", " ", "$last_name"]},
                "regex": word_boundary_pattern,
                "options": "i"
            }
        }},
        # Also include substring search as fallback for partial names
        {"first_name": {"$regex": q, "$options": "i"}},
        {"last_name": {"$regex": q, "$options": "i"}},
        # Search by phone number (exact or partial)
        {"phone_number": {"$regex": q, "$options": "i"}},
        # Search by guardian number (exact or partial)
        {"guardian_number": {"$regex": q, "$options": "i"}}
    ]
    
    # Add student_id search if query is numeric
    try:
        student_id_num = int(q)
        search_criteria.append({"student_id": student_id_num})
        search_criteria.append({"uid": student_id_num})
    except ValueError:
        # Query is not numeric, skip student_id search
        pass
    
    # Build the final search query
    search_query = {"$or": search_criteria}
    
    # Create list to hold all filters
    filters = [{"$or": search_criteria}]
    
    # Add level filter if specified
    if level is not None:
        filters.append({"level": level})
    
    # Add group filter if specified
    if group is not None:
        # Find the group by name to get student IDs
        group_doc = await Group.find_one(Group.group_name == group)
        if group_doc:
            # Convert ObjectIds to strings for matching
            student_object_ids = [str(student_id) for student_id in group_doc.students]
            filters.append({"_id": {"$in": [ObjectId(id_str) for id_str in student_object_ids]}})
        else:
            # Group not found, return empty result
            return []
    
    # Combine all filters
    if len(filters) > 1:
        search_query = {"$and": filters}
    else:
        search_query = filters[0]
    
    # Get all matching students (newest first)
    students = await students_collection.find(search_query).sort([("_id", -1)]).to_list(length=None)
    
    result = []
    for student in students:
        student["id"] = str(student["_id"])
        del student["_id"]
        student.setdefault("is_subscription", False)
        student.setdefault("uid", 0)

        # Attach group name
        group = await Group.find(Group.students == ObjectId(student["id"])).first_or_none()
        student["group"] = group.group_name if group else None

        result.append(StudentOut(**student))

    return result


@router.get("/sales", summary="Get all sales (monthsales and booksales) with pagination and filtering")
async def get_all_sales(
    page: int = Query(1, ge=1, description="Page number (starts from 1)"),
    limit: int = Query(25, ge=1, le=100, description="Number of items per page"),
    subscription_type: Optional[str] = Query(None, regex="^(monthsale|booksale)$", description="Filter by subscription type: monthsale or booksale"),
    student_name: Optional[str] = Query(None, description="Search by student name (first name, last name, or full name)"),
    level: Optional[int] = Query(None, ge=1, le=3, description="Filter by student level (1, 2, or 3)"),
    group_name: Optional[str] = Query(None, description="Filter by group name")
):
    """
    Get all sales (monthsales and booksales) with pagination and optional filtering.
    
    Returns combined data from both monthsales and booksales collections with:
    - Student name
    - Student level
    - Student group
    - Subscription type (monthsale or booksale)
    - Month (for monthsales) or Book name (for booksales)
    - Price
    - Date (created_at)
    
    Args:
        page: Page number (starts from 1)
        limit: Number of items per page (max 100)
        subscription_type: Optional filter - 'monthsale' or 'booksale'
        student_name: Optional search by student name (partial matching supported)
        level: Optional filter by student level (1, 2, or 3)
        group_name: Optional filter by group name
    """
    sales_data = []
    
    # Get filtered student IDs if group filter is applied
    filtered_student_ids = None
    if group_name:
        group_doc = await Group.find_one(Group.group_name == group_name)
        if group_doc:
            filtered_student_ids = group_doc.students
        else:
            # Group not found, return empty result
            return {
                "data": [],
                "pagination": {
                    "current_page": page,
                    "total_pages": 0,
                    "total_items": 0,
                    "items_per_page": limit,
                    "items_on_page": 0,
                    "has_next": False,
                    "has_prev": False
                },
                "message": f"Group '{group_name}' not found"
            }
    
    # Helper function to check if student matches all filters
    def matches_student_filters(student):
        # Check name filter
        if student_name:
            search_lower = student_name.lower()
            first_name = student.get('first_name', '').lower()
            last_name = student.get('last_name', '').lower()
            full_name = f"{first_name} {last_name}"
            
            name_match = (search_lower in first_name or 
                         search_lower in last_name or 
                         search_lower in full_name)
            if not name_match:
                return False
        
        # Check level filter
        if level is not None:
            if student.get('level') != level:
                return False
        
        # Check group filter (if filtered_student_ids is set)
        if filtered_student_ids is not None:
            student_object_id = ObjectId(student['_id'])
            if student_object_id not in filtered_student_ids:
                return False
        
        return True
    
    # Get monthsales if not filtering for booksales only
    if subscription_type != "booksale":
        monthsales = await MonthlySale.find_all().to_list()
        for sale in monthsales:
            # Get student info
            student = await students_collection.find_one({"_id": sale.student_id})
            if student and matches_student_filters(student):
                # Get group for student
                group = await Group.find(Group.students == ObjectId(student['_id'])).first_or_none()
                
                sales_data.append({
                    "id": sale.id,
                    "student_name": f"{student['first_name']} {student['last_name']}",
                    "student_level": student.get('level'),
                    "student_group": group.group_name if group else None,
                    "subscription_type": "monthsale",
                    "month_or_book": sale.month.strftime("%Y-%m") if sale.month else None,
                    "price": float(sale.price),
                    "date": sale.created_at,
                    "_sort_date": sale.created_at  # For sorting
                })
    
    # Get booksales if not filtering for monthsales only
    if subscription_type != "monthsale":
        booksales = await BookSale.find_all().to_list()
        for sale in booksales:
            # Get student info
            student = await students_collection.find_one({"_id": sale.student_id})
            if student and matches_student_filters(student):
                # Get group for student
                group = await Group.find(Group.students == ObjectId(student['_id'])).first_or_none()
                
                sales_data.append({
                    "id": sale.id,
                    "student_name": f"{student['first_name']} {student['last_name']}",
                    "student_level": student.get('level'),
                    "student_group": group.group_name if group else None,
                    "subscription_type": "booksale",
                    "month_or_book": sale.name,  # Book name
                    "price": float(sale.price),
                    "date": sale.created_at,
                    "_sort_date": sale.created_at  # For sorting
                })
    
    # Sort by date (newest first)
    sales_data.sort(key=lambda x: x["_sort_date"], reverse=True)
    
    # Remove the sorting field from response
    for item in sales_data:
        del item["_sort_date"]
    
    # Calculate pagination
    total_items = len(sales_data)
    total_pages = (total_items + limit - 1) // limit  # Ceiling division
    has_next = page < total_pages
    has_prev = page > 1
    
    # Apply pagination
    start_idx = (page - 1) * limit
    end_idx = start_idx + limit
    paginated_data = sales_data[start_idx:end_idx]
    
    # Format dates as strings for JSON response
    for item in paginated_data:
        if isinstance(item["date"], datetime):
            item["date"] = item["date"].isoformat()
    
    return {
        "data": paginated_data,
        "pagination": {
            "current_page": page,
            "total_pages": total_pages,
            "total_items": total_items,
            "items_per_page": limit,
            "items_on_page": len(paginated_data),
            "has_next": has_next,
            "has_prev": has_prev
        },
        "message": f"Sales data (Page {page} of {total_pages})" + 
                  (f" - Filtered by type: {subscription_type}" if subscription_type else "") +
                  (f" - Search: '{student_name}'" if student_name else "")
    }


@router.get("/", response_model=PaginatedStudentsResponse)
async def get_all_students(
    page: int = Query(1, ge=1, description="Page number (starts from 1)"),
    limit: int = Query(25, ge=1, le=100, description="Number of items per page (max 100)"),
    q: Optional[str] = Query(None, description="Search query for student name, phone number, or student ID"),
    level: Optional[int] = Query(None, ge=1, le=3, description="Filter by student level (1, 2, or 3)"),
    group: Optional[str] = Query(None, description="Filter by group name")
):
    """
    Get all students with optional search and filtering, plus pagination.
    
    Args:
        page: Page number (starts from 1)
        limit: Number of items per page (max 100)
        q: Optional search query (name, phone, or student ID)
        level: Optional filter by student level (1, 2, or 3)
        group: Optional filter by group name
    """
    await update_students_subscription_status()
    await archive_unpaid_students()
    
    # Build search and filter query
    search_query = {}
    
    # Add search functionality if q parameter is provided
    if q:
        # Build search criteria with improved Arabic name matching
        # Create word-boundary aware regex pattern for Arabic names
        # This will match the query as a separate word or at word boundaries
        word_boundary_pattern = f"(^|\\s){q}(\\s|$)"
        
        search_criteria = [
            # Search by first name - exact word match (case-insensitive)
            {"first_name": {"$regex": word_boundary_pattern, "$options": "i"}},
            # Search by last name - exact word match (case-insensitive)
            {"last_name": {"$regex": word_boundary_pattern, "$options": "i"}},
            # Search by full name - exact word match (case-insensitive)
            {"$expr": {
                "$regexMatch": {
                    "input": {"$concat": ["$first_name", " ", "$last_name"]},
                    "regex": word_boundary_pattern,
                    "options": "i"
                }
            }},
            # Also include substring search as fallback for partial names
            {"first_name": {"$regex": q, "$options": "i"}},
            {"last_name": {"$regex": q, "$options": "i"}},
            # Search by phone number (exact or partial)
            {"phone_number": {"$regex": q, "$options": "i"}},
            # Search by guardian number (exact or partial)
            {"guardian_number": {"$regex": q, "$options": "i"}}
        ]
        
        # Add student_id search if query is numeric
        try:
            student_id_num = int(q)
            search_criteria.append({"student_id": student_id_num})
            search_criteria.append({"uid": student_id_num})
        except ValueError:
            # Query is not numeric, skip student_id search
            pass
        
        # Create list to hold all filters
        filters = [{"$or": search_criteria}]
        
        # Add level filter if specified
        if level is not None:
            filters.append({"level": level})
        
        # Add group filter if specified
        if group is not None:
            # Find the group by name to get student IDs
            group_doc = await Group.find_one(Group.group_name == group)
            if group_doc:
                # Convert ObjectIds to strings for matching
                student_object_ids = [str(student_id) for student_id in group_doc.students]
                filters.append({"_id": {"$in": [ObjectId(id_str) for id_str in student_object_ids]}})
            else:
                # Group not found, return empty result
                return PaginatedStudentsResponse(
                    students=[],
                    total=0,
                    page=page,
                    limit=limit,
                    total_pages=0,
                    has_next=False,
                    has_prev=False
                )
        
        # Combine all filters
        if len(filters) > 1:
            search_query = {"$and": filters}
        else:
            search_query = filters[0]
    else:
        # No search query, but check for level and group filters
        filters = []
        
        # Add level filter if specified
        if level is not None:
            filters.append({"level": level})
        
        # Add group filter if specified
        if group is not None:
            # Find the group by name to get student IDs
            group_doc = await Group.find_one(Group.group_name == group)
            if group_doc:
                # Convert ObjectIds to strings for matching
                student_object_ids = [str(student_id) for student_id in group_doc.students]
                filters.append({"_id": {"$in": [ObjectId(id_str) for id_str in student_object_ids]}})
            else:
                # Group not found, return empty result
                return PaginatedStudentsResponse(
                    students=[],
                    total=0,
                    page=page,
                    limit=limit,
                    total_pages=0,
                    has_next=False,
                    has_prev=False
                )
        
        # Combine filters if any exist
        if len(filters) > 1:
            search_query = {"$and": filters}
        elif len(filters) == 1:
            search_query = filters[0]
        # If no filters, search_query remains empty dict (all documents)
    
    # Get total count with filters applied
    total = await students_collection.count_documents(search_query)
    
    # Calculate skip from page number
    skip = (page - 1) * limit
    
    # Get students with pagination and filters (newest first)
    students = await students_collection.find(search_query).sort([("_id", -1)]).skip(skip).limit(limit).to_list(length=None)
    result = []
    for student in students:
        student["id"] = str(student["_id"])
        del student["_id"]
        student.setdefault("is_subscription", False)
        student.setdefault("uid", 0)

        # Attach group name
        group = await Group.find(Group.students == ObjectId(student["id"])).first_or_none()
        student["group"] = group.group_name if group else None

        result.append(StudentOut(**student))

    # Calculate pagination metadata
    total_pages = (total + limit - 1) // limit  # Ceiling division
    has_next = page < total_pages
    has_prev = page > 1

    return PaginatedStudentsResponse(
        students=result,
        total=total,
        page=page,
        limit=limit,
        total_pages=total_pages,
        has_next=has_next,
        has_prev=has_prev
    )




@router.get("/{student_id}", response_model=StudentOut)
async def get_student_by_id(student_id: int):
    student = await students_collection.find_one({"student_id": student_id})
    if student is None:
        raise HTTPException(status_code=404, detail="Student not found")

    student["id"] = str(student["_id"])
    del student["_id"]
    student.setdefault("is_subscription", False)
    student.setdefault("uid", 0)

    # Find group(s) for this student
    group = await Group.find(Group.students == ObjectId(student["id"])).first_or_none()
    student["group"] = group.group_name if group else None

    return StudentOut(**student)


@router.put("/{student_id}", response_model=dict)
async def update_student(student_id: int, student_update: StudentUpdate):
    update_data = {k: v for k, v in student_update.model_dump().items() if v is not None}
    if not update_data:
        raise HTTPException(status_code=400, detail="No data provided for update")

    result = await students_collection.update_one({"student_id": student_id}, {"$set": update_data})
    if result.modified_count == 0:
        raise HTTPException(status_code=404, detail="Student not found or nothing changed")

    return {"message": "Student updated successfully"}


@router.delete("/{student_id}")
async def delete_student(student_id: int, request: Request):
    # Delete from MongoDB
    result = await students_collection.delete_one({"student_id": student_id})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Student not found")

    # Notify fingerprint backend with auth headers
    try:
        # Get auth token from request headers
        token = request.headers.get("authorization")
        headers = {"Authorization": token} if token else {}
        
        async with httpx.AsyncClient() as client:
            response = await client.delete(
                f"{HOST_REMOTE_URL}/students/delete_fingerprint/{student_id}",
                headers=headers
            )
            response.raise_for_status()
    except httpx.HTTPError as e:
        raise HTTPException(status_code=500, detail=f"Student deleted from DB, but failed to remove from fingerprint device: {str(e)}")

    return {"message": "Student deleted from DB and fingerprint device"}

@router.post("/{student_id}/archive")
async def archive_student_endpoint(student_id: int, request: ArchiveRequest = ArchiveRequest()):
    """Archive a student by moving them to the archived collection"""
    try:
        archived_student = await move_student_to_archive(student_id, request.archive_reason)
        return {
            "message": f"Student {student_id} archived successfully",
            "archived_student": archived_student
        }
    except Exception as e:
        raise HTTPException(status_code=404, detail=str(e))
    
# Pre-sync validation endpoint
@router.post("/validate-sync")
async def validate_sync_all_students(request: Request):
    """
    Validate students before syncing to fingerprint backend.
    This checks for potential issues without actually performing the sync.
    """
    try:
        # Get auth token from request headers
        token = request.headers.get("authorization")
        if not token:
            raise HTTPException(status_code=401, detail="Authorization token required")
        
        # Get all students from main database
        print("🔍 Validating students for sync...")
        all_students = await students_collection.find({}).to_list(length=None)
        
        if not all_students:
            return {
                "success": True,
                "message": "No students found in main database",
                "total_students": 0,
                "validation_results": []
            }
        
        total_students = len(all_students)
        print(f"📊 Validating {total_students} students")
        
        validation_results = []
        issues_count = 0
        
        # Validate each student
        for i, student in enumerate(all_students, 1):
            student_info = {
                "student_id": student.get("student_id"),
                "uid": student.get("uid"),
                "name": f"{student.get('first_name', '')} {student.get('last_name', '')}",
                "phone": student.get("phone_number")
            }
            
            issues = []
            
            # Check for missing required fields
            required_fields = ['student_id', 'uid', 'first_name', 'last_name', 'phone_number']
            for field in required_fields:
                if not student.get(field):
                    issues.append(f"Missing {field}")
            
            # Check birth_date format
            if student.get("birth_date"):
                birth_date = student["birth_date"]
                try:
                    if hasattr(birth_date, 'isoformat'):
                        birth_date.isoformat()
                    elif not isinstance(birth_date, str):
                        issues.append(f"Invalid birth_date format: {type(birth_date).__name__}")
                except Exception as e:
                    issues.append(f"Birth date error: {str(e)}")
            
            # Check for duplicate UIDs (this could cause conflicts)
            uid = student.get("uid")
            if uid:
                duplicate_uid_count = sum(1 for s in all_students if s.get("uid") == uid)
                if duplicate_uid_count > 1:
                    issues.append(f"Duplicate UID {uid} found {duplicate_uid_count} times")
            
            # Check phone number format
            phone = student.get("phone_number")
            if phone and len(str(phone)) < 10:
                issues.append("Phone number seems too short")
            
            validation_result = {
                **student_info,
                "has_issues": len(issues) > 0,
                "issues": issues
            }
            
            if issues:
                issues_count += 1
                print(f"⚠️ [{i}/{total_students}] Issues found for {student_info['name']}: {', '.join(issues)}")
            else:
                print(f"✅ [{i}/{total_students}] No issues for {student_info['name']}")
            
            validation_results.append(validation_result)
        
        # Summary
        clean_students = total_students - issues_count
        print(f"\n📋 Validation completed!")
        print(f"📊 Total students: {total_students}")
        print(f"✅ Students with no issues: {clean_students}")
        print(f"⚠️ Students with issues: {issues_count}")
        
        return {
            "success": True,
            "message": f"Validation completed: {clean_students}/{total_students} students are ready for sync",
            "summary": {
                "total_students": total_students,
                "clean_students": clean_students,
                "students_with_issues": issues_count
            },
            "validation_results": validation_results,
            "students_with_issues": [result for result in validation_results if result["has_issues"]],
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        print(f"💥 Error in validation: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Validation failed: {str(e)}")


# Bulk sync all students to fingerprint backend
@router.post("/sync-all-to-fingerprint")
async def sync_all_students_to_fingerprint(request: Request):
    """
    Sync ALL students from main database to fingerprint backend.
    This endpoint is for one-time migration of existing students.
    
    Use this when you have students in main DB that were never synced to fingerprint backend.
    """
    try:
        # Get auth token from request headers
        token = request.headers.get("authorization")
        if not token:
            raise HTTPException(status_code=401, detail="Authorization token required")
        
        headers = {"Authorization": token}
        
        # Get all students from main database
        print("🔄 Starting bulk sync of all students to fingerprint backend...")
        all_students = await students_collection.find({}).to_list(length=None)
        
        if not all_students:
            return {
                "success": True,
                "message": "No students found in main database",
                "total_students": 0,
                "synced_count": 0,
                "failed_count": 0,
                "results": []
            }
        
        total_students = len(all_students)
        print(f"📊 Found {total_students} students to sync")
        
        synced_count = 0
        failed_count = 0
        sync_results = []
        
        # Process each student
        for i, student in enumerate(all_students, 1):
            student_info = {
                "student_id": student.get("student_id"),
                "uid": student.get("uid"),
                "name": f"{student.get('first_name', '')} {student.get('last_name', '')}",
                "phone": student.get("phone_number")
            }
            
            print(f"🔄 [{i}/{total_students}] Syncing {student_info['name']} (UID: {student_info['uid']})...")
            
            try:
                # Fix birth_date handling
                birth_date_str = None
                if student.get("birth_date"):
                    birth_date = student["birth_date"]
                    if hasattr(birth_date, 'isoformat'):
                        birth_date_str = birth_date.isoformat()
                    elif isinstance(birth_date, str):
                        birth_date_str = birth_date
                    else:
                        birth_date_str = str(birth_date)
                
                # Prepare data for fingerprint backend (same format as create_student)
                sync_data = {
                    "uid": student.get("uid"),
                    "student_id": str(student.get("student_id")),
                    "first_name": student.get("first_name"),
                    "last_name": student.get("last_name"),
                    "email": student.get("email"),
                    "phone_number": student.get("phone_number"),
                    "guardian_number": student.get("guardian_number"),
                    "birth_date": birth_date_str,
                    "national_id": student.get("national_id"),
                    "gender": student.get("gender"),
                    "level": student.get("level"),
                    "school_name": student.get("school_name"),
                    "is_subscription": student.get("is_subscription", False),  # Use actual value, default to False
                    "fingerprint_template": None  # No fingerprint template for bulk sync
                }
                
                # Send to fingerprint backend
                async with httpx.AsyncClient(timeout=30) as client:
                    response = await client.post(
                        f"{HOST_REMOTE_URL}/students/sync-from-main",
                        json=sync_data,
                        headers=headers
                    )
                    
                    if response.status_code == 200:
                        synced_count += 1
                        sync_results.append({
                            **student_info,
                            "status": "success",
                            "message": "Successfully synced"
                        })
                        print(f"✅ [{i}/{total_students}] Successfully synced {student_info['name']}")
                    elif response.status_code == 409:  # Student already exists
                        synced_count += 1
                        sync_results.append({
                            **student_info,
                            "status": "skipped",
                            "message": "Student already exists in fingerprint backend"
                        })
                        print(f"⏭️ [{i}/{total_students}] Student {student_info['name']} already exists - skipped")
                    else:
                        failed_count += 1
                        error_detail = f"HTTP {response.status_code}: {response.text}"
                        sync_results.append({
                            **student_info,
                            "status": "failed",
                            "message": error_detail
                        })
                        print(f"❌ [{i}/{total_students}] Failed to sync {student_info['name']}: {error_detail}")
                        
            except httpx.TimeoutException:
                failed_count += 1
                sync_results.append({
                    **student_info,
                    "status": "failed",
                    "message": "Request timeout"
                })
                print(f"⏰ [{i}/{total_students}] Timeout syncing {student_info['name']}")
                
            except httpx.RequestError as e:
                failed_count += 1
                sync_results.append({
                    **student_info,
                    "status": "failed",
                    "message": f"Request error: {str(e)}"
                })
                print(f"🔌 [{i}/{total_students}] Network error syncing {student_info['name']}: {str(e)}")
                
            except Exception as e:
                failed_count += 1
                sync_results.append({
                    **student_info,
                    "status": "failed",
                    "message": f"Unexpected error: {str(e)}"
                })
                print(f"💥 [{i}/{total_students}] Unexpected error syncing {student_info['name']}: {str(e)}")
        
        # Final summary
        success_rate = (synced_count / total_students * 100) if total_students > 0 else 0
        
        print(f"\n🎉 Bulk sync completed!")
        print(f"📊 Total students: {total_students}")
        print(f"✅ Successfully synced: {synced_count}")
        print(f"❌ Failed to sync: {failed_count}")
        print(f"📈 Success rate: {success_rate:.1f}%")
        
        return {
            "success": True,
            "message": f"Bulk sync completed: {synced_count}/{total_students} students synced successfully",
            "summary": {
                "total_students": total_students,
                "synced_count": synced_count,
                "failed_count": failed_count,
                "success_rate": round(success_rate, 2)
            },
            "results": sync_results,
            "failed_students": [result for result in sync_results if result["status"] == "failed"],
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"💥 Critical error in bulk sync: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Bulk sync failed: {str(e)}")


# New Excel upload endpoint for bulk adding students
@router.post("/excel-upload", response_model=ExcelUploadResponse)
async def upload_students_excel(file: UploadFile = File(...)):
    if not file.filename.endswith(('.xlsx', '.xls')):
        raise HTTPException(status_code=400, detail="Invalid file format. Please upload an Excel file (xlsx/xls).")

    try:
        # Read the file content into memory
        contents = await file.read()
        
        # Try to read with headers first
        df = pd.read_excel(contents)
        
        # Check if we have proper English headers
        english_required = ['first_name', 'last_name', 'phone_number', 'guardian_number', 'gender', 'level', 'is_subscription']
        
        # If no proper headers found, assume data starts from first row without headers
        if not any(col in df.columns for col in english_required):
            # Read again without headers and assign column names based on position
            df = pd.read_excel(contents, header=None)
            # Your data structure: first_name, middle_name, last_name, email, phone, guardian, gender, level, school, subscription
            if len(df.columns) >= 10:
                df.columns = ['first_name', 'middle_name', 'last_name', 'email', 'phone_number', 'guardian_number', 'gender', 'level', 'school_name', 'is_subscription']
                # Combine middle_name + last_name into last_name
                df['last_name'] = df['middle_name'].astype(str) + ' ' + df['last_name'].astype(str)
                # Drop the middle_name column as we don't need it anymore
                df = df.drop('middle_name', axis=1)
            else:
                raise HTTPException(status_code=400, detail=f"Expected at least 10 columns, got {len(df.columns)}")
                
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Could not read Excel file: {e}")

    # Now check for required columns after processing
    required_columns = ['first_name', 'last_name', 'phone_number', 'guardian_number', 'gender', 'level', 'is_subscription']
    missing_cols = [col for col in required_columns if col not in df.columns]
    if missing_cols:
        raise HTTPException(status_code=400, detail=f"Missing required columns in Excel: {missing_cols}")

    results = []
    successful_creations = 0
    failed_creations = 0

    # Iterate rows
    for i, row in df.iterrows():
        student_dict: Dict[str, Any] = row.to_dict()
        row_result = StudentCreationResult(row_number=i+1,  # Since we removed headers, start from 1
                                           success=False,
                                           student_data=student_dict)
        
        # Skip if this looks like a header row (contains Arabic headers)
        if (str(student_dict.get('first_name', '')).strip() in ['الاسم الاول', 'first_name'] or
            str(student_dict.get('gender', '')).strip() in ['الجنس', 'gender']):
            continue
            
        # Format corrections
        try:
            # Type fixes
            if 'birth_date' in student_dict and pd.notnull(student_dict['birth_date']):
                if isinstance(student_dict['birth_date'], pd.Timestamp):
                    student_dict['birth_date'] = student_dict['birth_date'].date()
            
            # Gender conversion - Handle Arabic gender values
            if 'gender' in student_dict and student_dict['gender']:
                gender_val = str(student_dict['gender']).strip()
                if gender_val == 'ذكر':
                    student_dict['gender'] = 'male'
                elif gender_val == 'انثي':
                    student_dict['gender'] = 'female'
                else:
                    student_dict['gender'] = gender_val.lower()
            
            # Level conversion
            if 'level' in student_dict:
                try:
                    student_dict['level'] = int(row['level'])
                except Exception:
                    row_result.error = 'Invalid value for level'
                    failed_creations += 1
                    results.append(row_result)
                    continue
            
            # Bool conversion for subscription
            if 'is_subscription' in student_dict:
                v = student_dict['is_subscription']
                if isinstance(v, str):
                    student_dict['is_subscription'] = v.strip().lower() in ['true', '1', 'yes']
                else:
                    student_dict['is_subscription'] = bool(v)

            # Create student logic (reuse endpoint logic)
            student_create_schema = StudentCreate(**student_dict)
            # Use internal create_student flow (reuse most checks, use helper to mimic request)
            created = await create_student(student_create_schema)
            row_result.success = True
            row_result.student_id = created.student_id
            successful_creations += 1
        except HTTPException as httpe:
            row_result.error = str(httpe.detail)
            failed_creations += 1
        except Exception as ex:
            row_result.error = str(ex)
            failed_creations += 1
        results.append(row_result)

    summary = f"{successful_creations} students created, {failed_creations} failed"
    return ExcelUploadResponse(
        total_rows=len(df),
        successful_creations=successful_creations,
        failed_creations=failed_creations,
        results=results,
        summary=summary
    )



