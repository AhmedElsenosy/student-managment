from fastapi import APIRouter, HTTPException, status, Depends, Query
from fastapi.encoders import jsonable_encoder
from app.dependencies.auth import get_current_assistant
from app.database import student_collection
from bson import ObjectId
from datetime import datetime
from app.schemas.archived_student import ArchivedStudentOut, ArchiveRequest, PaginatedArchivedStudentsResponse
from typing import List, Any, Dict, Optional
from app.models.archived_student import ArchivedStudentModel

# Helper function to convert ObjectIds to strings recursively
def convert_objectids_to_strings(obj: Any) -> Any:
    if isinstance(obj, ObjectId):
        return str(obj)
    elif isinstance(obj, dict):
        return {key: convert_objectids_to_strings(value) for key, value in obj.items()}
    elif isinstance(obj, list):
        return [convert_objectids_to_strings(item) for item in obj]
    else:
        return obj

router = APIRouter(
    prefix="/archive",
    tags=["Archive Management"],
    dependencies=[Depends(get_current_assistant)]
)

# ✅ Helper to move student by _id
async def move_student_to_archive(student_id: str, archive_reason: str):
    if not ObjectId.is_valid(student_id):
        raise HTTPException(status_code=400, detail="Invalid student ObjectId")

    student = await student_collection.find_one({"_id": ObjectId(student_id)})

    if not student:
        raise HTTPException(status_code=404, detail="Student not found")

    student["archived"] = True
    student["archive_reason"] = archive_reason
    student["archived_at"] = datetime.utcnow()
    student["months_without_payment"] = 0

    archived_student = ArchivedStudentModel(**student)
    await archived_student.insert()

    await student_collection.delete_one({"_id": ObjectId(student_id)})

    return archived_student

@router.post("/{student_id}")
async def archive_student(student_id: str, request: ArchiveRequest):
    archived_student = await move_student_to_archive(student_id, request.archive_reason)
    return {
        "message": f"Student {student_id} archived successfully",
        "archived_student": jsonable_encoder(archived_student)
    }

@router.post("/{student_id}/restore")
async def restore_student(student_id: str):
    if not ObjectId.is_valid(student_id):
        raise HTTPException(status_code=400, detail="Invalid ObjectId")

    from app.database import archived_student_collection
    archived_student = await archived_student_collection.find_one({"_id": ObjectId(student_id)})

    if not archived_student:
        raise HTTPException(status_code=404, detail="Archived student not found")

    archived_student["archived"] = False
    archived_student["archive_reason"] = None
    archived_student["archived_at"] = None

    await student_collection.insert_one(archived_student)
    await archived_student_collection.delete_one({"_id": ObjectId(student_id)})

    return {"message": f"Student {student_id} restored successfully"}

@router.get("/search", response_model=List[dict])
async def search_archived_students(
    q: str = Query(..., description="Search query for student name, phone number, or student ID"),
    level: Optional[int] = Query(None, ge=1, le=3, description="Filter by student level (1, 2, or 3)")
):
    """
    Search for archived students by name, phone number, or student ID with optional level filtering.
    Supports partial matching and case-insensitive search.
    Returns all matching results without pagination.
    
    Args:
        q: Search query (name, phone, or student ID)
        level: Optional filter by student level (1, 2, or 3)
    """
    from app.database import archived_student_collection
    
    try:
        # Build search query with multiple criteria
        search_criteria = [
            # Search by first name (case-insensitive, partial match)
            {"first_name": {"$regex": q, "$options": "i"}},
            # Search by last name (case-insensitive, partial match)
            {"last_name": {"$regex": q, "$options": "i"}},
            # Search by full name (first + last)
            {"$expr": {
                "$regexMatch": {
                    "input": {"$concat": ["$first_name", " ", "$last_name"]},
                    "regex": q,
                    "options": "i"
                }
            }},
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
        
        # Combine all filters
        if len(filters) > 1:
            search_query = {"$and": filters}
        else:
            search_query = filters[0]
        
        # Get all matching archived students (newest first by archived_at)
        archived_students = await archived_student_collection.find(search_query).sort([("archived_at", -1)]).to_list(length=None)
        
        # Convert all ObjectId fields to strings recursively
        result = [convert_objectids_to_strings(student) for student in archived_students]
        
        return result
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/", response_model=PaginatedArchivedStudentsResponse)
async def get_all_archived_students(
    page: int = Query(1, ge=1, description="Page number (starts from 1)"),
    limit: int = Query(25, ge=1, le=100, description="Number of items per page (max 100)"),
    q: Optional[str] = Query(None, description="Search query for student name, phone number, or student ID"),
    level: Optional[int] = Query(None, ge=1, le=3, description="Filter by student level (1, 2, or 3)")
):
    """
    Get all archived students with optional search and filtering, plus pagination.
    
    Args:
        page: Page number (starts from 1)
        limit: Number of items per page (max 100)
        q: Optional search query (name, phone, or student ID)
        level: Optional filter by student level (1, 2, or 3)
    """
    from app.database import archived_student_collection
    try:
        # Build search and filter query
        search_query = {}
        
        # Add search functionality if q parameter is provided
        if q:
            # Build search criteria with multiple criteria (similar to regular students)
            search_criteria = [
                # Search by first name (case-insensitive, partial match)
                {"first_name": {"$regex": q, "$options": "i"}},
                # Search by last name (case-insensitive, partial match)
                {"last_name": {"$regex": q, "$options": "i"}},
                # Search by full name (first + last)
                {"$expr": {
                    "$regexMatch": {
                        "input": {"$concat": ["$first_name", " ", "$last_name"]},
                        "regex": q,
                        "options": "i"
                    }
                }},
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
            
            # Combine all filters
            if len(filters) > 1:
                search_query = {"$and": filters}
            else:
                search_query = filters[0]
        else:
            # No search query, but check for level filter
            if level is not None:
                search_query = {"level": level}
            # If no filters, search_query remains empty dict (all documents)
        
        # Get total count with filters applied
        total = await archived_student_collection.count_documents(search_query)
        
        # Calculate skip from page number
        skip = (page - 1) * limit
        
        # Get archived students with pagination and filters (newest first by archived_at)
        archived = await archived_student_collection.find(search_query).sort([("archived_at", -1)]).skip(skip).limit(limit).to_list(length=None)

        # Convert all ObjectId fields to strings recursively
        archived = [convert_objectids_to_strings(student) for student in archived]
        
        # Calculate pagination metadata
        total_pages = (total + limit - 1) // limit  # Ceiling division
        has_next = page < total_pages
        has_prev = page > 1

        return PaginatedArchivedStudentsResponse(
            archived_students=archived,
            total=total,
            page=page,
            limit=limit,
            total_pages=total_pages,
            has_next=has_next,
            has_prev=has_prev
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/{student_id}")
async def get_archived_student(student_id: str):
    from app.database import archived_student_collection

    try:
        student = await archived_student_collection.find_one({"_id": ObjectId(student_id)})
        if not student:
            raise HTTPException(status_code=404, detail="Archived student not found")

        # Convert ObjectId to string
        student["_id"] = str(student["_id"])

        return jsonable_encoder(student)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/{student_id}")
async def permanently_delete_archived_student(student_id: str):
    from app.database import archived_student_collection
    if not ObjectId.is_valid(student_id):
        raise HTTPException(status_code=400, detail="Invalid ObjectId")
    result = await archived_student_collection.delete_one({"_id": ObjectId(student_id)})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Archived student not found")
    return {"message": f"Archived student {student_id} permanently deleted"}
