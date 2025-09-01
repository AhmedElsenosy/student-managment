from beanie import Document, PydanticObjectId
from pydantic import Field
from datetime import time
from enum import Enum
from typing import List, Any
from beanie import Document
from pydantic import BaseModel, Field
from bson import ObjectId
from pydantic_core import core_schema
from pydantic import GetCoreSchemaHandler
from pymongo import IndexModel, ASCENDING



class PyObjectId(ObjectId):
    @classmethod
    def __get_pydantic_core_schema__(cls, source_type: Any, handler: GetCoreSchemaHandler) -> core_schema.CoreSchema:
        return core_schema.no_info_plain_validator_function(cls._validate)

    @classmethod
    def _validate(cls, value, *args, **kwargs):
        if isinstance(value, ObjectId):
            return value
        if not ObjectId.is_valid(value):
            raise ValueError("Invalid ObjectId")
        return ObjectId(value)

    @classmethod
    def __get_json_schema__(cls, core_schema, handler):
        return {"type": "string"}

class DayOfWeek(str, Enum):
    saturday = "Saturday"
    sunday = "Sunday"
    monday = "Monday"
    tuesday = "Tuesday"
    wednesday = "Wednesday"
    thursday = "Thursday"
    friday = "Friday"


class Group(Document):
    id: PyObjectId = Field(default_factory=PyObjectId, alias="_id")
    group_name: str
    start_time: str
    level: int = Field(..., ge=1, le=3)
    days: List[DayOfWeek]
    students: List[PyObjectId] = []

    class Settings:
        name = "groups"
        indexes = [
            # Index on group_name for fast group lookups by name (attendance optimized)
            IndexModel(
                [("group_name", ASCENDING)],
                name="groups_name_index"
            ),
            # Index on students array for fast membership lookups
            IndexModel(
                [("students", ASCENDING)],
                name="groups_students_index"
            ),
            # Index on level for filtering groups by level
            IndexModel(
                [("level", ASCENDING)],
                name="groups_level_index"
            ),
            # Compound index for level and group name
            IndexModel(
                [("level", ASCENDING), ("group_name", ASCENDING)],
                name="groups_level_name_compound_index"
            ),
            # ========================================
            # ATTENDANCE ENDPOINT OPTIMIZATION INDEXES
            # ========================================
            # Compound index for students array + level (optimizes group filtering in attendance)
            IndexModel(
                [("students", ASCENDING), ("level", ASCENDING)],
                name="students_level_compound_index"
            )
        ]
