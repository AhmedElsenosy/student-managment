from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form, Query
from datetime import date, datetime
from typing import List, Optional
from pathlib import Path
from bson import ObjectId
import shutil
import os

from app.dependencies.auth import get_current_assistant
from app.models.exam import ExamModel
from app.models.student import StudentModel
from app.models.common import PyObjectId  
from app.schemas.student import ExamEntryCreate
from app.schemas.exam import ExamCreate, ExamUpdate, ExamOut, PaginatedExamsResponse
from app.models.student_document import StudentDocument, ExamEntry
from app.database import db

students_collection = db["students"]
exams_collection = db["exams"]



router = APIRouter(prefix="/exams", tags=["Exams"])

UPLOAD_DIR = "upload/solutions"
os.makedirs(UPLOAD_DIR, exist_ok=True)

@router.post("/debug/test-upload")
async def test_file_upload(
    model_1_solution: UploadFile = File(None),
    model_2_solution: UploadFile = File(None), 
    model_3_solution: UploadFile = File(None),
    assistant=Depends(get_current_assistant)
):
    """Debug endpoint to test file uploads"""
    results = []
    
    model_files = [
        (model_1_solution, "Model 1"),
        (model_2_solution, "Model 2"), 
        (model_3_solution, "Model 3")
    ]
    
    for model_file, model_name in model_files:
        result = {
            "model": model_name,
            "file_received": model_file is not None,
            "has_filename": hasattr(model_file, 'filename') if model_file else False,
            "filename": model_file.filename if model_file and hasattr(model_file, 'filename') else None,
            "content_type": model_file.content_type if model_file and hasattr(model_file, 'content_type') else None,
            "size": model_file.size if model_file and hasattr(model_file, 'size') else "unknown"
        }
        results.append(result)
    
    return {
        "message": "File upload test completed",
        "upload_dir": UPLOAD_DIR,
        "upload_dir_exists": os.path.exists(UPLOAD_DIR),
        "results": results
    }

@router.post("/", response_model=ExamOut)
async def create_exam(
    exam_name: str = Form(...),
    exam_level: int = Form(...),
    exam_date: date = Form(...),
    exam_start_time: str = Form(...),
    final_degree: int = Form(...),
    solution_photo: UploadFile = File(None),  # Legacy field
    exam_models_pdf: UploadFile = File(None),  # NEW: PDF with 3 models
    model_1_solution: UploadFile = File(None),
    model_2_solution: UploadFile = File(None), 
    model_3_solution: UploadFile = File(None),
    model_1_name: str = Form("Model A"),
    model_2_name: str = Form("Model B"),
    model_3_name: str = Form("Model C"),
    assistant=Depends(get_current_assistant)
):
    # Legacy solution photo handling
    photo_path = None
    if solution_photo:
        photo_path = f"{UPLOAD_DIR}/{solution_photo.filename}"
        with open(photo_path, "wb") as f:
            shutil.copyfileobj(solution_photo.file, f)

    # NEW: Process PDF with 3 models if provided
    pdf_generated_models = []
    if exam_models_pdf and hasattr(exam_models_pdf, 'filename') and exam_models_pdf.filename:
        try:
            # Import PDF converter
            import sys
            import os
            sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
            from pdf_converter import PDFConverter
            
            # Save uploaded PDF temporarily
            pdf_filename = f"exam_models_{exam_name}_{exam_models_pdf.filename}"
            temp_pdf_path = f"{UPLOAD_DIR}/{pdf_filename}"
            
            with open(temp_pdf_path, "wb") as f:
                shutil.copyfileobj(exam_models_pdf.file, f)
            
            print(f"📄 Processing PDF: {temp_pdf_path}")
            
            # Convert PDF to images
            converter = PDFConverter(dpi=300)
            image_paths = converter.convert_pdf_to_images(temp_pdf_path, UPLOAD_DIR)
            
            # Take first 3 images as the 3 models
            model_names = [model_1_name, model_2_name, model_3_name]
            for i, image_path in enumerate(image_paths[:3]):
                model_number = i + 1
                model_name = model_names[i] if i < len(model_names) else f"Model {chr(65+i)}"
                
                # Rename image to match model convention
                final_model_path = f"{UPLOAD_DIR}/model_{model_number}_{os.path.basename(image_path)}"
                shutil.move(image_path, final_model_path)
                
                pdf_generated_models.append((final_model_path, model_name, model_number))
                print(f"✅ Generated model {model_number} ({model_name}): {final_model_path}")
            
            # Clean up original PDF and any extra images
            if os.path.exists(temp_pdf_path):
                os.remove(temp_pdf_path)
            for extra_image in image_paths[3:]:
                if os.path.exists(extra_image):
                    os.remove(extra_image)
                    
        except Exception as e:
            print(f"❌ Error processing PDF: {str(e)}")
            # Continue with normal flow if PDF processing fails
            pass

    # Handle 3 model solutions (individual files or from PDF)
    models = []
    
    # If we have PDF-generated models, use those, otherwise use individual files
    if pdf_generated_models:
        # Use PDF-generated models
        for model_path, model_name, model_number in pdf_generated_models:
            from app.models.exam import ExamModelVariant
            models.append(ExamModelVariant(
                model_number=model_number,
                model_name=model_name,
                solution_photo=model_path
            ))
    else:
        # Use individual uploaded files (original flow)
        model_files = [
            (model_1_solution, model_1_name, 1),
            (model_2_solution, model_2_name, 2), 
            (model_3_solution, model_3_name, 3)
        ]
        
        for model_file, model_name, model_number in model_files:
            model_path = None
            if model_file and hasattr(model_file, 'filename') and model_file.filename and model_file.filename.strip():
                # Create unique filename to avoid conflicts
                model_filename = f"model_{model_number}_{model_file.filename}"
                model_path = f"{UPLOAD_DIR}/{model_filename}"
                
                try:
                    # Save the uploaded file
                    with open(model_path, "wb") as f:
                        shutil.copyfileobj(model_file.file, f)
                    print(f"✅ Saved model {model_number} solution: {model_path}")
                except Exception as e:
                    print(f"❌ Failed to save model {model_number} solution: {str(e)}")
                    model_path = None
            else:
                print(f"⚠️  No file uploaded for model {model_number} ({model_name})")
            
            from app.models.exam import ExamModelVariant
            models.append(ExamModelVariant(
                model_number=model_number,
                model_name=model_name,
                solution_photo=model_path
            ))

    exam_data = ExamCreate(
        exam_name=exam_name,
        exam_level=exam_level,
        exam_date=exam_date,
        exam_start_time=exam_start_time,
        final_degree=final_degree,
        solution_photo=photo_path
    )

    exam = ExamModel(**exam_data.dict())
    exam.models = models  # Add the 3 models
    await exam.insert()
    exam_data = exam.dict(by_alias=True)
    exam_data["id"] = str(exam_data.pop("_id"))
    return ExamOut(**exam_data)



@router.get("/", response_model=PaginatedExamsResponse)
async def get_all_exams(
    page: int = Query(1, ge=1, description="Page number (starts from 1)"),
    limit: int = Query(25, ge=1, le=100, description="Number of items per page (max 100)"),
    q: Optional[str] = Query(None, description="Search query for exam name"),
    exam_date: Optional[date] = Query(None, description="Filter exams by specific date (YYYY-MM-DD)"),
    level: Optional[int] = Query(None, ge=1, le=3, description="Filter by exam level (1, 2, or 3)"),
    assistant=Depends(get_current_assistant)
):
    """
    Get all exams with optional search and filtering, plus pagination.
    
    Args:
        page: Page number (starts from 1)
        limit: Number of items per page (max 100)
        q: Optional search query for exam name
        exam_date: Optional filter by specific exam date (YYYY-MM-DD)
        level: Optional filter by exam level (1, 2, or 3)
    """
    # Build search and filter query using MongoDB syntax
    mongo_query = {}
    query_conditions = []
    
    # Add search functionality if q parameter is provided
    if q:
        # Search by exam name (case-insensitive, partial match)
        query_conditions.append({"exam_name": {"$regex": q, "$options": "i"}})
    
    # Add date filtering if provided - filter by specific date
    if exam_date:
        # Convert date to string format that matches database storage
        date_str = exam_date.strftime("%Y-%m-%d")
        print(f"🔍 Date filter: Looking for exam_date = '{date_str}'")
        
        # Try both string format and datetime range
        # MongoDB can't serialize Python date objects, so we use datetime objects
        start_of_day = datetime.combine(exam_date, datetime.min.time())
        end_of_day = datetime.combine(exam_date, datetime.max.time())
        
        date_query = {
            "$or": [
                {"exam_date": date_str},  # String format (YYYY-MM-DD)
                {"exam_date": {"$gte": start_of_day, "$lte": end_of_day}}  # DateTime range
            ]
        }
        
        query_conditions.append(date_query)
    
    # Add level filter if specified
    if level is not None:
        query_conditions.append({"exam_level": level})
    
    # Combine all conditions
    if query_conditions:
        if len(query_conditions) > 1:
            mongo_query = {"$and": query_conditions}
        else:
            mongo_query = query_conditions[0]
    # If no conditions, mongo_query remains empty {}
    
    # Debug: Print the final query
    print(f"🔍 Final MongoDB query: {mongo_query}")
    
    # Get total count with filters applied
    if mongo_query:
        total = await exams_collection.count_documents(mongo_query)
        print(f"🔍 Found {total} exams matching the query")
    else:
        total = await exams_collection.count_documents({})
        print(f"🔍 No filters applied, total exams: {total}")
    
    # Calculate skip from page number
    skip = (page - 1) * limit
    
    # Get exams with pagination and filters (sorted by exam_date descending - newest first)
    if mongo_query:
        exams = await exams_collection.find(mongo_query).sort("exam_date", -1).skip(skip).limit(limit).to_list(length=None)
    else:
        exams = await exams_collection.find({}).sort("exam_date", -1).skip(skip).limit(limit).to_list(length=None)
    
    students = await students_collection.find().to_list(length=None)
    
    exam_list = []
    for exam in exams:
        exam_id = str(exam["_id"])
        # Count students who have this exam in their exams list
        count = sum(
            any(str(entry.get("exam_id", "")) == exam_id for entry in student.get("exams", []))
            for student in students
        )
        exam["id"] = exam_id
        exam["student_count"] = count
        exam_list.append(ExamOut(**exam))
    
    # Calculate pagination metadata
    total_pages = (total + limit - 1) // limit  # Ceiling division
    has_next = page < total_pages
    has_prev = page > 1
    
    return PaginatedExamsResponse(
        exams=exam_list,
        total=total,
        page=page,
        limit=limit,
        total_pages=total_pages,
        has_next=has_next,
        has_prev=has_prev
    )


@router.put("/{exam_id}", response_model=ExamOut)
async def update_exam(
    exam_id: str,
    exam_name: str = Form(None),
    exam_level: int = Form(None),
    exam_date: date = Form(None),
    exam_start_time: str = Form(None),
    final_degree: int = Form(None),
    solution_photo: UploadFile = File(None),
    assistant=Depends(get_current_assistant)
):
    exam = await ExamModel.get(exam_id)
    if not exam:
        raise HTTPException(status_code=404, detail="Exam not found")

    update_data = {
        "exam_name": exam_name,
        "exam_level": exam_level,
        "exam_date": exam_date,
        "exam_start_time": exam_start_time,
        "final_degree": final_degree
    }

    
    update_data = {k: v for k, v in update_data.items() if v is not None}

    
    if solution_photo:
        photo_path = f"{UPLOAD_DIR}/{solution_photo.filename}"
        with open(photo_path, "wb") as f:
            shutil.copyfileobj(solution_photo.file, f)
        update_data["solution_photo"] = photo_path

    for key, value in update_data.items():
        setattr(exam, key, value)

    await exam.save()
    return ExamOut(**exam.dict(exclude={"id", "_id"}), id=str(exam.id))


@router.delete("/{exam_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_exam(exam_id: str, assistant=Depends(get_current_assistant)):
    exam = await ExamModel.get(exam_id)
    if not exam:
        raise HTTPException(status_code=404, detail="Exam not found")
    await exam.delete()



STUDENT_SOLUTION_DIR = "upload/student_solutions"

@router.post("/{exam_id}/students")
async def add_student_to_exam(
    exam_id: str,
    student_id: str = Form(...),
    student_degree: int = Form(...),
    degree_percentage: float = Form(...),
    delivery_time: datetime = Form(...),
    solution_photo: UploadFile = File(None),
    assistant=Depends(get_current_assistant)
):
    student = await StudentDocument.get(ObjectId(student_id))
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")

    exam = await ExamModel.get(exam_id)
    if not exam:
        raise HTTPException(status_code=404, detail="Exam not found")

    solution_path = None
    if solution_photo:
        filename = Path(solution_photo.filename).name
        os.makedirs(STUDENT_SOLUTION_DIR, exist_ok=True)
        solution_path = f"{STUDENT_SOLUTION_DIR}/{filename}"
        with open(solution_path, "wb") as f:
            shutil.copyfileobj(solution_photo.file, f)

    new_entry = ExamEntry(
        exam_id=str(exam.id),
        degree=student_degree,
        percentage=degree_percentage,
        delivery_time=delivery_time,
        solution_photo=solution_path
    )

    student.exams.append(new_entry)
    await student.save()

    return {"msg": "Student exam record added successfully"}



@router.get("/{exam_id}/students")
async def get_students_for_exam(exam_id: str, assistant=Depends(get_current_assistant)):
    # Fetch exam
    exam = await exams_collection.find_one({"_id": ObjectId(exam_id)})
    if not exam:
        raise HTTPException(status_code=404, detail="Exam not found")

    # Extract exam info
    exam_details = {
        "exam_id": str(exam["_id"]),
        "exam_name": exam["exam_name"],
        "exam_level": exam["exam_level"],
        "exam_date": exam["exam_date"],
        "exam_start_time": exam["exam_start_time"],
        "final_degree": exam["final_degree"],
        "solution_photo": exam.get("solution_photo")
    }

    # Search students who participated
    students = await students_collection.find().to_list(length=None)
    entered_students = []
    for student in students:
        for entry in student.get("exams", []):
            if str(entry.get("exam_id", "")) == exam_id:
                entered_students.append({
                    "student_id": student["student_id"],
                    "first_name": student["first_name"],
                    "last_name": student["last_name"],
                    "phone_number": student["phone_number"],
                    "guardian_number": student["guardian_number"],
                    "degree": entry.get("degree"),
                    "percentage": entry.get("percentage"),
                    "delivery_time": entry.get("delivery_time")
                })

    return {
        "exam": exam_details,
        "student_count": len(entered_students),
        "students": entered_students
    }

# Exam correction endpoints have been moved to the fingerprint backend
# Students should submit their solutions to the fingerprint backend at:
# POST /exams/{exam_id}/submit
# POST /exams/{exam_id}/students/{student_id}/correct

from pydantic import BaseModel

class ManualCorrectionRequest(BaseModel):
    exam_id: str
    student_uid: int
    student_degree: int
    model_number: int = 1
    notes: str = None

@router.post("/manual-correction")
async def manual_exam_correction(
    data: ManualCorrectionRequest,
    assistant=Depends(get_current_assistant)
):
    """
    Manually grade a student's exam.
    
    This endpoint allows assistants to manually enter exam grades for students
    without requiring the student to submit through the fingerprint system.
    
    Parameters:
    - exam_id: The ID of the exam to correct
    - student_uid: The UID of the student to grade
    - student_degree: The grade achieved by the student
    - model_number: Which exam model the student used (1, 2, or 3)
    - notes: Optional notes about the correction
    - solution_photo: Optional photo of student's solution
    """
    # 1. Validate the exam exists
    exam = await ExamModel.get(data.exam_id)
    if not exam:
        raise HTTPException(status_code=404, detail="Exam not found")
    
    # 2. Validate the student exists
    student = await StudentModel.find_one(StudentModel.uid == data.student_uid)
    if not student:
        raise HTTPException(status_code=404, detail=f"Student with UID {data.student_uid} not found")
    
    # 3. Validate the student degree is within range
    if data.student_degree < 0 or data.student_degree > exam.final_degree:
        raise HTTPException(
            status_code=400, 
            detail=f"Student degree must be between 0 and {exam.final_degree}"
        )
    
    # 4. Validate model number
    if data.model_number < 1 or data.model_number > 3:
        raise HTTPException(status_code=400, detail="Model number must be 1, 2, or 3")
        
    # 5. Calculate percentage
    degree_percentage = (data.student_degree / exam.final_degree) * 100
    
    # 6. Check if student already has this exam
    existing_exam_entry = None
    for entry in student.exams:
        if str(entry.exam_id) == data.exam_id:
            existing_exam_entry = entry
            break
    
    # 7. Create or update the exam entry
    if existing_exam_entry:
        # Update existing entry
        existing_exam_entry.student_degree = data.student_degree
        existing_exam_entry.degree_percentage = degree_percentage
        existing_exam_entry.delivery_time = datetime.now()
        # Update model number (if not already set)
        if not hasattr(existing_exam_entry, 'model_number') or existing_exam_entry.model_number is None:
            existing_exam_entry.model_number = data.model_number
        # Update notes (if not already set)
        if data.notes and (not hasattr(existing_exam_entry, 'notes') or not existing_exam_entry.notes):
            existing_exam_entry.notes = data.notes
    else:
        # Create new entry
        new_entry = ExamEntry(
            exam_id=data.exam_id,
            exam_name=exam.exam_name,  # Store exam name for convenience
            student_degree=data.student_degree,
            degree_percentage=degree_percentage,
            delivery_time=datetime.now(),
            model_number=data.model_number,
            notes=data.notes
        )
        student.exams.append(new_entry)
    
    # 8. Save student data
    await student.save()
    
    # 9. Return success response with details
    return {
        "success": True,
        "message": f"Exam grade recorded successfully",
        "details": {
            "exam": {
                "id": str(exam.id),
                "name": exam.exam_name,
                "level": exam.exam_level,
                "final_degree": exam.final_degree
            },
            "student": {
                "uid": student.uid,
                "name": f"{student.first_name} {student.last_name}",
                "level": student.level
            },
            "grade": {
                "degree": data.student_degree,
                "percentage": round(degree_percentage, 2),
                "model_number": data.model_number,
                "has_solution_photo": False,
                "timestamp": datetime.now().isoformat()
            }
        }
    }


@router.get("/student/{student_uid}")
async def get_student_exams(
    student_uid: int,
    assistant=Depends(get_current_assistant)
):
    """
    Get all exam data for a specific student by their UID.
    
    This endpoint returns all exams that the student has taken,
    including their grades, percentages, and exam details.
    
    Parameters:
    - student_uid: The UID of the student
    
    Returns:
    - Student information
    - List of all exams taken by the student
    - Summary statistics
    """
    # 1. Find the student by UID
    student = await StudentModel.find_one(StudentModel.uid == student_uid)
    if not student:
        raise HTTPException(status_code=404, detail=f"Student with UID {student_uid} not found")
    
    # 2. Get all exams from the database for reference
    all_exams = await exams_collection.find({}).to_list(length=None)
    exam_lookup = {str(exam["_id"]): exam for exam in all_exams}
    
    # 3. Process student's exam entries
    student_exams = []
    total_score = 0
    total_possible = 0
    
    for exam_entry in student.exams:
        exam_id = str(exam_entry.exam_id)
        exam_info = exam_lookup.get(exam_id)
        
        if exam_info:
            # Calculate stats for this exam with null safety
            student_degree = getattr(exam_entry, 'student_degree', None) or 0
            degree_percentage = getattr(exam_entry, 'degree_percentage', None) or 0
            
            # Ensure numeric values
            student_degree = student_degree if isinstance(student_degree, (int, float)) else 0
            degree_percentage = degree_percentage if isinstance(degree_percentage, (int, float)) else 0
            final_degree = exam_info.get("final_degree", 0) or 0
            
            total_score += student_degree
            total_possible += final_degree
            
            student_exam_data = {
                "exam_id": exam_id,
                "exam_name": exam_info.get("exam_name", "Unknown Exam"),
                "exam_level": exam_info.get("exam_level"),
                "exam_date": exam_info.get("exam_date"),
                "exam_start_time": exam_info.get("exam_start_time"),
                "final_degree": final_degree,
                "student_degree": student_degree,
                "degree_percentage": round(degree_percentage, 2),
                "delivery_time": exam_entry.delivery_time,
                "model_number": getattr(exam_entry, 'model_number', None),
                "notes": getattr(exam_entry, 'notes', None),
                "has_solution_photo": bool(getattr(exam_entry, 'solution_photo', None))
            }
            student_exams.append(student_exam_data)
        else:
            # Exam no longer exists in database, but keep the record
            student_degree = getattr(exam_entry, 'student_degree', None) or 0
            degree_percentage = getattr(exam_entry, 'degree_percentage', None) or 0
            
            # Ensure numeric values
            student_degree = student_degree if isinstance(student_degree, (int, float)) else 0
            degree_percentage = degree_percentage if isinstance(degree_percentage, (int, float)) else 0
            
            student_exam_data = {
                "exam_id": exam_id,
                "exam_name": getattr(exam_entry, 'exam_name', "Deleted Exam"),
                "exam_level": None,
                "exam_date": None,
                "exam_start_time": None,
                "final_degree": None,
                "student_degree": student_degree,
                "degree_percentage": round(degree_percentage, 2),
                "delivery_time": exam_entry.delivery_time,
                "model_number": getattr(exam_entry, 'model_number', None),
                "notes": getattr(exam_entry, 'notes', None),
                "has_solution_photo": bool(getattr(exam_entry, 'solution_photo', None)),
                "exam_deleted": True
            }
            student_exams.append(student_exam_data)
    
    # 4. Sort exams by delivery time (most recent first)
    student_exams.sort(key=lambda x: x["delivery_time"] if x["delivery_time"] else datetime.min, reverse=True)
    
    return {
        "success": True,
        "student": {
            "uid": student.uid,
            "name": f"{student.first_name} {student.last_name}",
            "level": student.level,
            "phone_number": student.phone_number,
            "guardian_number": student.guardian_number,
            "email": student.email,
            "student_id": student.student_id
        },
        "exams": student_exams
    }

