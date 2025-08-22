from pydantic import BaseModel, Field
from bson import ObjectId
from datetime import date, datetime
from typing import Optional, List, Dict
from beanie import Document
from app.schemas.student import ExamEntry

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

    class Config:
        arbitrary_types_allowed = True
        json_encoders = {ObjectId: str}
