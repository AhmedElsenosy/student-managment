from pydantic import BaseModel, Field, field_validator
from datetime import time
from typing import Optional, List, Union
from enum import Enum
from beanie import PydanticObjectId
from app.models.group import PyObjectId

class DayOfWeek(str, Enum):
    saturday = "Saturday"
    sunday = "Sunday"
    monday = "Monday"
    tuesday = "Tuesday"
    wednesday = "Wednesday"
    thursday = "Thursday"
    friday = "Friday"


class GroupCreate(BaseModel):
    group_name: str
    start_time: str
    level: int = Field(..., ge=1, le=3)
    days: List[DayOfWeek]


class GroupUpdate(BaseModel):
    group_name: Optional[str] = None
    start_time: Optional[str] = None
    level: Optional[int] = None
    days: Optional[List[DayOfWeek]] = None


class GroupOut(BaseModel):
    id: str
    group_name: str
    start_time: Union[time, str]
    level: int
    days: List[DayOfWeek]
    student_count: int = 0
    
    @field_validator('start_time', mode='before')
    @classmethod
    def parse_time(cls, v):
        if isinstance(v, str):
            # Handle both "7:00" and "07:00" formats
            if ':' in v:
                parts = v.split(':')
                if len(parts) == 2:
                    hour = parts[0].zfill(2)  # Pad with zero if needed
                    minute = parts[1].zfill(2)  # Pad with zero if needed
                    return f"{hour}:{minute}"
        return v

class AddStudentToGroup(BaseModel):
    student_id: PyObjectId


class StudentInGroupOut(BaseModel):
    student_name: str
    level: int
    phone_number: str
    guardian_number: str
    is_subscription: bool
    group_name: str

class GroupWithStudentsOut(BaseModel):
    group_id: str
    group_name: str
    level: int
    students: List[StudentInGroupOut]