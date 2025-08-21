from fastapi import APIRouter, HTTPException, status, Depends, Query
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
async def create_student(student: StudentCreate):
    student_data = student.dict()

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

    # Insert into DB
    result = await students_collection.insert_one(student_data)
    student_data["id"] = str(result.inserted_id)

    return StudentOut(**student_data)



@router.get("/", response_model=PaginatedStudentsResponse)
async def get_all_students(page: int = 1, limit: int = 25):
    await update_students_subscription_status()
    await archive_unpaid_students()
    # Get total count
    total = await students_collection.count_documents({})
    
    # Calculate skip from page number
    skip = (page - 1) * limit
    
    # Get students with pagination (newest first)
    students = await students_collection.find().sort([("_id", -1)]).skip(skip).limit(limit).to_list(length=None)
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
async def delete_student(student_id: int):
    # Delete from MongoDB
    result = await students_collection.delete_one({"student_id": student_id})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Student not found")

    # Notify fingerprint backend
    try:
        async with httpx.AsyncClient() as client:
            response = await client.delete(f"{HOST_REMOTE_URL}/students/delete_fingerprint/{student_id}")
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



