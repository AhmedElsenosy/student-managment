from pydantic import BaseModel, Field
from bson import ObjectId
from datetime import date, datetime
from typing import Optional, List, Dict
from beanie import Document, Indexed
from pymongo import IndexModel, TEXT, ASCENDING
from app.schemas.student import ExamEntry
from app.models.py_object_id import PyObjectId

class StudentModel(Document):  
    id: PyObjectId = Field(default_factory=PyObjectId, alias="_id")
    student_id: int
    first_name: str
    last_name: str
    email: Optional[str] = None
    phone_number: str
    guardian_number: str
    birth_date: Optional[date] = None
    national_id: Optional[str] = None
    gender: str
    level: int
    school_name: Optional[str] = None
    is_subscription: bool
    created_at: date
    exams: List[ExamEntry] = []
    fingerprint_template: Optional[str] = None
    uid: int
    attendance: Dict[str, bool] = Field(default_factory=dict)
    created_at: datetime
    subscription: Optional[Dict[str, Dict[str, float]]] = Field(default_factory=dict)
    months_without_payment: int = Field(default=0)
    archived: bool = Field(default=False)

    class Settings:
        name = "students"
        indexes = [
            # Text index for name searching - enables fast text search on names
            IndexModel(
                [("first_name", TEXT), ("last_name", TEXT)],
                name="name_text_index"
            ),
            # Regular index for phone number - fast exact/prefix matching
            IndexModel(
                [("phone_number", ASCENDING)],
                name="phone_number_index"
            ),
            # Compound index for level + name searches
            IndexModel(
                [("level", ASCENDING), ("first_name", ASCENDING), ("last_name", ASCENDING)],
                name="level_name_compound_index"
            ),
            # Index for UID searches (used in attendance)
            IndexModel(
                [("uid", ASCENDING)],
                name="uid_index",
                unique=True
            ),
            # Index for student_id searches
            IndexModel(
                [("student_id", ASCENDING)],
                name="student_id_index",
                unique=True
            ),
            # Index for subscription status filtering
            IndexModel(
                [("is_subscription", ASCENDING)],
                name="subscription_status_index"
            ),
            # Index for archived status filtering
            IndexModel(
                [("archived", ASCENDING)],
                name="archived_status_index"
            ),
            # Index for guardian number - enables regex search compatibility with text search
            IndexModel(
                [("guardian_number", ASCENDING)],
                name="guardian_number_index"
            ),
            # ========================================
            # ATTENDANCE PERFORMANCE INDEXES
            # ========================================
            # Core attendance index - for students with attendance records
            IndexModel(
                [("attendance", ASCENDING)],
                name="attendance_exists_index",
                partialFilterExpression={"attendance": {"$exists": True}}
            ),
            # Compound index for attendance + level filtering (get_all_absent_students, get_all_present_students)
            IndexModel(
                [("attendance", ASCENDING), ("level", ASCENDING)],
                name="attendance_level_index",
                partialFilterExpression={"attendance": {"$exists": True}}
            ),
            # Compound index for attendance + name searches (search functionality in attendance endpoints)
            IndexModel(
                [("attendance", ASCENDING), ("first_name", ASCENDING), ("last_name", ASCENDING)],
                name="attendance_name_index",
                partialFilterExpression={"attendance": {"$exists": True}}
            ),
            # Comprehensive compound index for all attendance filtering scenarios
            IndexModel(
                [("attendance", ASCENDING), ("level", ASCENDING), ("first_name", ASCENDING), ("last_name", ASCENDING)],
                name="attendance_comprehensive_index",
                partialFilterExpression={"attendance": {"$exists": True}}
            ),
            # Individual name indexes for better regex search performance
            IndexModel(
                [("first_name", ASCENDING)],
                name="first_name_index"
            ),
            IndexModel(
                [("last_name", ASCENDING)],
                name="last_name_index"
            ),
            # Level index for level-based filtering
            IndexModel(
                [("level", ASCENDING)],
                name="level_index"
            )
        ]

    class Config:
        arbitrary_types_allowed = True
        json_encoders = {ObjectId: str}