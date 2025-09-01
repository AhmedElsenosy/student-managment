from pydantic import BaseModel, Field
from bson import ObjectId
from datetime import date, datetime
from typing import Optional, List, Dict
from beanie import Document
from app.schemas.student import ExamEntry
from pymongo import IndexModel, ASCENDING, DESCENDING, TEXT

class ArchivedStudentModel(Document):
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
    archived_at: datetime = Field(default_factory=datetime.utcnow)
    archive_reason: Optional[str] = None

    class Settings:
        name = "archived_students"
        indexes = [
            # Text index for name searching - enables fast text search on names
            IndexModel(
                [("first_name", TEXT), ("last_name", TEXT)],
                name="archived_name_text_index"
            ),
            # Individual name indexes for exact matching
            IndexModel(
                [("first_name", ASCENDING)],
                name="archived_first_name_index"
            ),
            IndexModel(
                [("last_name", ASCENDING)],
                name="archived_last_name_index"
            ),
            # Phone number index for contact searches
            IndexModel(
                [("phone_number", ASCENDING)],
                name="archived_phone_number_index"
            ),
            # Guardian number index
            IndexModel(
                [("guardian_number", ASCENDING)],
                name="archived_guardian_number_index"
            ),
            # Student ID index for quick lookups
            IndexModel(
                [("student_id", ASCENDING)],
                name="archived_student_id_index"
            ),
            # UID index
            IndexModel(
                [("uid", ASCENDING)],
                name="archived_uid_index"
            ),
            # Archive date index for chronological queries
            IndexModel(
                [("archived_at", DESCENDING)],
                name="archived_date_index"
            ),
            # Level index for filtering
            IndexModel(
                [("level", ASCENDING)],
                name="archived_level_index"
            ),
            # Archive reason index for categorization
            IndexModel(
                [("archive_reason", ASCENDING)],
                name="archived_reason_index"
            ),
            # Compound index for level and name searches
            IndexModel(
                [("level", ASCENDING), ("first_name", ASCENDING), ("last_name", ASCENDING)],
                name="archived_level_name_compound_index"
            ),
            # Compound index for date and level
            IndexModel(
                [("archived_at", DESCENDING), ("level", ASCENDING)],
                name="archived_date_level_compound_index"
            )
        ]

    class Config:
        arbitrary_types_allowed = True
        json_encoders = {ObjectId: str}
