# app/models/common.py
from bson import ObjectId
from pydantic import BaseModel
from datetime import datetime
from typing import Optional

class PyObjectId(ObjectId):
    """Custom ObjectId that works with Pydantic v2"""
    
    @classmethod
    def __get_pydantic_core_schema__(cls, source_type, handler):
        from pydantic_core import core_schema
        return core_schema.with_info_plain_validator_function(
            cls._pydantic_validate,
            serialization=core_schema.to_string_ser_schema()
        )
    
    @classmethod
    def _pydantic_validate(cls, value, info=None):
        if isinstance(value, ObjectId):
            return value  # Return the ObjectId directly
        if isinstance(value, str) and ObjectId.is_valid(value):
            return ObjectId(value)  # Return a regular ObjectId
        raise ValueError(f"Invalid ObjectId: {value}")
    
    @classmethod
    def __get_pydantic_json_schema__(cls, schema, handler):
        schema = handler(schema)
        schema.update(type="string", format="objectid")
        return schema

class ExamEntry(BaseModel):
    exam_id: PyObjectId
    exam_name: Optional[str] = None
    student_degree: Optional[int] = None
    degree_percentage: Optional[float] = None
    delivery_time: Optional[datetime] = None
    solution_photo: Optional[str] = None

    class Config:
        arbitrary_types_allowed = True
        json_encoders = {ObjectId: str}
