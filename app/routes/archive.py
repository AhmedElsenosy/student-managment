from datetime import datetime, timedelta, date
from bson import ObjectId
from app.database import student_collection, archived_student_collection
from app.models.archived_student import ArchivedStudentModel
from app.models.student import StudentModel

def get_month_key(date):
    return date.strftime("%Y-%m")

async def archive_unpaid_students():
    today = datetime.now()
    current_month = get_month_key(today)
    last_month = get_month_key(today.replace(day=1) - timedelta(days=1))

    async for student in student_collection.find():
        student_id = student["_id"]
        subscription = student.get("subscription", {})
        monthsales = subscription.get("monthsales", {})

        # 🚫 Skip students with fewer than 2 months of payment history
        if len(monthsales) < 2:
            continue

        paid_this_month = current_month in monthsales
        paid_last_month = last_month in monthsales

        # 📌 Count months without payment
        if paid_this_month:
            months_without_payment = 0
        elif paid_last_month:
            months_without_payment = 1
        else:
            months_without_payment = 2  # Missed 2 months in a row

        # Update the field for tracking
        await student_collection.update_one(
            {"_id": student_id},
            {"$set": {"months_without_payment": months_without_payment}}
        )

        # 📦 Archive only if unpaid for 2 consecutive months
        if months_without_payment >= 2 and not student.get("archived", False):
            student["archived_at"] = today
            student["archive_reason"] = "Unpaid for 2 consecutive months"
            student["archived"] = True

            # Convert date objects to datetime for BSON compatibility
            student_data = student.copy()
            if "birth_date" in student_data and student_data["birth_date"] is not None:
                if isinstance(student_data["birth_date"], date) and not isinstance(student_data["birth_date"], datetime):
                    student_data["birth_date"] = datetime.combine(student_data["birth_date"], datetime.min.time())
            
            # Use direct MongoDB insert to avoid Pydantic validation issues
            await archived_student_collection.insert_one(student_data)

            # Delete the student from the student collection
            await student_collection.delete_one({"_id": student_id})

async def move_student_to_archive(student_id: int, archive_reason: str):
    student = await student_collection.find_one({"student_id": student_id})
    if not student:
        raise Exception("Student not found")
    
    archived_student_data = student.copy()
    archived_student_data["archived_at"] = datetime.utcnow()
    archived_student_data["archive_reason"] = archive_reason
    
    # Convert date objects to datetime for BSON compatibility
    if "birth_date" in archived_student_data and archived_student_data["birth_date"] is not None:
        if isinstance(archived_student_data["birth_date"], date) and not isinstance(archived_student_data["birth_date"], datetime):
            archived_student_data["birth_date"] = datetime.combine(archived_student_data["birth_date"], datetime.min.time())
    
    await archived_student_collection.insert_one(archived_student_data)
    await student_collection.delete_one({"student_id": student_id})
    
    return archived_student_data

async def restore_student_from_archive(student_id: int):
    """Move student from archived collection back to active students collection"""
    archived_student = await archived_student_collection.find_one({"student_id": student_id})
    if not archived_student:
        raise Exception("Archived student not found")
    
    # Remove archive-specific fields
    student_data = archived_student.copy()
    student_data.pop("archived_at", None)
    student_data.pop("archive_reason", None)
    student_data["archived"] = False
    student_data["months_without_payment"] = 0
    
    # Convert date objects to datetime for BSON compatibility
    if "birth_date" in student_data and student_data["birth_date"] is not None:
        if isinstance(student_data["birth_date"], date) and not isinstance(student_data["birth_date"], datetime):
            student_data["birth_date"] = datetime.combine(student_data["birth_date"], datetime.min.time())
    
    # Insert back into students collection
    await student_collection.insert_one(student_data)
    # Remove from archived collection
    await archived_student_collection.delete_one({"student_id": student_id})
    
    return student_data

async def get_archived_students():
    """Get all archived students"""
    archived_students = await archived_student_collection.find().to_list(length=None)
    result = []
    for student in archived_students:
        student["id"] = str(student["_id"])
        del student["_id"]
        result.append(student)
    return result

async def get_archived_student_by_id(student_id: int):
    """Get a specific archived student by ID"""
    student = await archived_student_collection.find_one({"student_id": student_id})
    if student:
        student["id"] = str(student["_id"])
        del student["_id"]
    return student
