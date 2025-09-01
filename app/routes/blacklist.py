from fastapi import APIRouter, HTTPException, Depends, Query
from typing import List, Optional
from bson import ObjectId
from datetime import datetime

from app.models.blacklist import BlacklistStudent
from app.models.student import StudentModel
from app.schemas.blacklist import BlacklistStudentRequest, BlacklistStudentResponse, RestoreStudentRequest, PaginatedBlacklistStudentsResponse
from app.dependencies.auth import get_current_assistant

router = APIRouter(prefix="/blacklist", tags=["Blacklist"])

@router.post("/add-student", response_model=BlacklistStudentResponse)
async def add_student_to_blacklist(
    data: BlacklistStudentRequest, 
    assistant=Depends(get_current_assistant)
):
    """
    Add a student to blacklist by moving them from students collection to blacklist collection
    """
    try:
        # Validate ObjectId
        student_object_id = ObjectId(data.student_object_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid student ObjectId")
    
    # Find the student in students collection
    student = await StudentModel.get(student_object_id)
    if not student:
        raise HTTPException(status_code=404, detail="Student not found in students collection")
    
    # Check if student is already in blacklist
    existing_blacklisted = await BlacklistStudent.find_one(
        BlacklistStudent.original_student_object_id == student_object_id
    )
    if existing_blacklisted:
        raise HTTPException(status_code=400, detail="Student is already in blacklist")
    
    # Create blacklist entry with all student data
    blacklist_student = BlacklistStudent(
        # Copy all original student data
        student_id=student.student_id,
        first_name=student.first_name,
        last_name=student.last_name,
        email=student.email,
        phone_number=student.phone_number,
        guardian_number=student.guardian_number,
        birth_date=student.birth_date,
        national_id=student.national_id,
        gender=student.gender,
        level=student.level,
        school_name=student.school_name,
        is_subscription=student.is_subscription,
        exams=student.exams if student.exams else [],
        uid=student.uid,
        attendance=student.attendance if student.attendance else {},
        subscription=student.subscription if student.subscription else {},
        months_without_payment=student.months_without_payment,
        created_at=student.created_at,
        
        # Blacklist specific data
        blacklisted_at=datetime.utcnow(),
        blacklist_reason=data.blacklist_reason,
        original_student_object_id=student_object_id
    )
    
    # Save to blacklist collection
    await blacklist_student.insert()
    
    # Delete from students collection
    await student.delete()
    
    return BlacklistStudentResponse(
        id=str(blacklist_student.id),
        student_id=blacklist_student.student_id,
        first_name=blacklist_student.first_name,
        last_name=blacklist_student.last_name,
        email=blacklist_student.email,
        phone_number=blacklist_student.phone_number,
        blacklisted_at=blacklist_student.blacklisted_at,
        blacklist_reason=blacklist_student.blacklist_reason,
        original_student_object_id=str(blacklist_student.original_student_object_id)
    )

@router.delete("/remove-student/{blacklist_id}")
async def remove_student_from_blacklist(
    blacklist_id: str,
    assistant=Depends(get_current_assistant)
):
    """
    Permanently delete a student from blacklist (complete removal from database)
    """
    try:
        # Validate ObjectId
        blacklist_object_id = ObjectId(blacklist_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid blacklist ObjectId")
    
    # Find the student in blacklist collection
    blacklist_student = await BlacklistStudent.get(blacklist_object_id)
    if not blacklist_student:
        raise HTTPException(status_code=404, detail="Student not found in blacklist")
    
    # Store student info for response before deletion
    student_name = f"{blacklist_student.first_name} {blacklist_student.last_name}"
    student_id = blacklist_student.student_id
    
    # Delete from blacklist collection (permanent deletion)
    await blacklist_student.delete()
    
    return {
        "detail": f"Student {student_name} (ID: {student_id}) has been permanently deleted from the database",
        "student_id": student_id,
        "deleted_at": datetime.utcnow().isoformat()
    }

@router.get("/", response_model=PaginatedBlacklistStudentsResponse)
async def get_all_blacklisted_students(
    page: int = Query(1, ge=1, description="Page number (starts from 1)"),
    limit: int = Query(25, ge=1, le=100, description="Number of items per page (max 100)"),
    q: Optional[str] = Query(None, description="Search query for student name, phone number, or student ID"),
    level: Optional[int] = Query(None, ge=1, le=3, description="Filter by student level (1, 2, or 3)"),
    assistant=Depends(get_current_assistant)
):
    """
    Get all blacklisted students with optional search and filtering, plus pagination.
    
    Args:
        page: Page number (starts from 1)
        limit: Number of items per page (max 100)
        q: Optional search query (name, phone, or student ID)
        level: Optional filter by student level (1, 2, or 3)
    """
    # Build search and filter query using MongoDB syntax
    mongo_query = {}
    
    # Add search functionality if q parameter is provided
    if q:
        # Handle full name search by splitting the search term for better matching
        search_terms = q.strip().split()
        search_criteria = []
        
        if len(search_terms) == 1:
            # Single term - search in both first and last name
            single_term = search_terms[0]
            search_criteria.extend([
                {"first_name": {"$regex": single_term, "$options": "i"}},
                {"last_name": {"$regex": single_term, "$options": "i"}},
                # Search by phone number (exact or partial)
                {"phone_number": {"$regex": single_term, "$options": "i"}},
                # Search by guardian number (exact or partial)
                {"guardian_number": {"$regex": single_term, "$options": "i"}}
            ])
        else:
            # Multiple terms - try different combinations for full name matching
            for term in search_terms:
                search_criteria.extend([
                    {"first_name": {"$regex": term, "$options": "i"}},
                    {"last_name": {"$regex": term, "$options": "i"}}
                ])
            
            # Also search for the full term in first or last name
            search_criteria.extend([
                {"first_name": {"$regex": q, "$options": "i"}},
                {"last_name": {"$regex": q, "$options": "i"}},
                # Search by phone number (exact or partial)
                {"phone_number": {"$regex": q, "$options": "i"}},
                # Search by guardian number (exact or partial)
                {"guardian_number": {"$regex": q, "$options": "i"}}
            ])
        
        # Add student_id search if query is numeric
        try:
            student_id_num = int(q)
            search_criteria.append({"student_id": student_id_num})
            search_criteria.append({"uid": student_id_num})
        except ValueError:
            # Query is not numeric, skip student_id search
            pass
        
        # Add search criteria to query
        if level is not None:
            # Combine search with level filter using $and
            mongo_query = {
                "$and": [
                    {"$or": search_criteria},
                    {"level": level}
                ]
            }
        else:
            mongo_query = {"$or": search_criteria}
    elif level is not None:
        # Only level filter, no search
        mongo_query = {"level": level}
    # If no search and no level filter, mongo_query remains empty {}
    
    # Get total count with filters applied
    if mongo_query:
        total = await BlacklistStudent.find(mongo_query).count()
    else:
        total = await BlacklistStudent.count()
    
    # Calculate skip from page number
    skip = (page - 1) * limit
    
    # Get blacklisted students with pagination and filters (newest first by blacklisted_at)
    if mongo_query:
        blacklisted_students = await BlacklistStudent.find(mongo_query).sort(["-blacklisted_at"]).skip(skip).limit(limit).to_list()
    else:
        blacklisted_students = await BlacklistStudent.find_all().sort(["-blacklisted_at"]).skip(skip).limit(limit).to_list()
    
    # Convert to response objects
    students_response = [
        BlacklistStudentResponse(
            id=str(student.id),
            student_id=student.student_id,
            first_name=student.first_name,
            last_name=student.last_name,
            email=student.email,
            phone_number=student.phone_number,
            blacklisted_at=student.blacklisted_at,
            blacklist_reason=student.blacklist_reason,
            original_student_object_id=str(student.original_student_object_id)
        )
        for student in blacklisted_students
    ]
    
    # Calculate pagination metadata
    total_pages = (total + limit - 1) // limit  # Ceiling division
    has_next = page < total_pages
    has_prev = page > 1
    
    return PaginatedBlacklistStudentsResponse(
        blacklist_students=students_response,
        total=total,
        page=page,
        limit=limit,
        total_pages=total_pages,
        has_next=has_next,
        has_prev=has_prev
    )

@router.get("/{blacklist_id}")
async def get_blacklisted_student_details(
    blacklist_id: str,
    assistant=Depends(get_current_assistant)
):
    """
    Get detailed information about a blacklisted student
    """
    try:
        blacklist_object_id = ObjectId(blacklist_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid blacklist ObjectId")
    
    blacklist_student = await BlacklistStudent.get(blacklist_object_id)
    if not blacklist_student:
        raise HTTPException(status_code=404, detail="Student not found in blacklist")
    
    return {
        "id": str(blacklist_student.id),
        "student_id": blacklist_student.student_id,
        "first_name": blacklist_student.first_name,
        "last_name": blacklist_student.last_name,
        "email": blacklist_student.email,
        "phone_number": blacklist_student.phone_number,
        "guardian_number": blacklist_student.guardian_number,
        "birth_date": blacklist_student.birth_date,
        "national_id": blacklist_student.national_id,
        "gender": blacklist_student.gender,
        "level": blacklist_student.level,
        "school_name": blacklist_student.school_name,
        "is_subscription": blacklist_student.is_subscription,
        "exams": blacklist_student.exams,
        "attendance": blacklist_student.attendance,
        "subscription": blacklist_student.subscription,
        "months_without_payment": blacklist_student.months_without_payment,
        "created_at": blacklist_student.created_at,
        "blacklisted_at": blacklist_student.blacklisted_at,
        "blacklist_reason": blacklist_student.blacklist_reason,
        "original_student_object_id": str(blacklist_student.original_student_object_id)
    }
