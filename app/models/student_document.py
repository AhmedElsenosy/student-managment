from beanie import Document
from datetime import date, datetime
from bson import ObjectId
from pydantic import Field
from typing import Optional, List
from pydantic import Field, BaseModel
from app.models.common import PyObjectId

class ExamEntry(BaseModel):
    exam_id: PyObjectId
    degree: Optional[float] = None
    percentage: Optional[float] = None
    delivery_time: Optional[datetime] = None
    solution_photo: Optional[str] = None


class StudentDocument(Document):
    id: ObjectId = Field(default_factory=ObjectId, alias="_id")
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
    is_subscription: Optional[bool] = Field(default=False)
    created_at: datetime
    exams: List[ExamEntry] = Field(default_factory=list)

    class Settings:
        name = "students"

    model_config = {
        "arbitrary_types_allowed": True
    }