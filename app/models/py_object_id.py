from bson import ObjectId
from typing import Any

class PyObjectId(ObjectId):
    """Custom ObjectId that works with Pydantic v2"""
    
    @classmethod
    def __get_pydantic_core_schema__(cls, source_type: Any, handler):
        from pydantic_core import core_schema
        return core_schema.with_info_plain_validator_function(
            cls._pydantic_validate,
            serialization=core_schema.to_string_ser_schema()
        )
    
    @classmethod
    def _pydantic_validate(cls, value: Any, info=None):
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
