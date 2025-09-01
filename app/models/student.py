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
            # Individual name indexes for better regex search performance
            IndexModel(
                [("first_name", ASCENDING)],
                name="first_name_index"
            ),
            IndexModel(
                [("last_name", ASCENDING)],
                name="last_name_index"
            )
        ]

    class Config:
        arbitrary_types_allowed = True
        json_encoders = {ObjectId: str}