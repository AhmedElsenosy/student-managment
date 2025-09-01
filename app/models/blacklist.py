from beanie import Document
from pydantic import Field, ConfigDict
from datetime import datetime, date
from typing import Optional, Dict, List, Any
from bson import ObjectId
from pymongo import IndexModel, ASCENDING, DESCENDING, TEXT

class BlacklistStudent(Document):
    model_config = ConfigDict(arbitrary_types_allowed=True)
    
    # Original student data
    student_id: int = Field(...)
    first_name: str = Field(...)
    last_name: str = Field(...)
    email: Optional[str] = Field(default=None)
    phone_number: str = Field(...)
    guardian_number: str = Field(...)
    birth_date: Optional[date] = Field(default=None)
    national_id: Optional[str] = Field(default=None)
    gender: str = Field(...)
    level: int = Field(...)
    school_name: Optional[str] = Field(default=None)
    is_subscription: bool = Field(...)
    exams: List[Dict[str, Any]] = Field(default_factory=list)
    uid: int = Field(...)
    attendance: Dict[str, Any] = Field(default_factory=dict)
    subscription: Dict[str, Any] = Field(default_factory=dict)
    months_without_payment: int = Field(default=0)
    archived: bool = Field(default=False)
    
    # Blacklist specific fields
    blacklisted_at: datetime = Field(default_factory=datetime.utcnow)
    blacklist_reason: Optional[str] = Field(default=None)
    original_student_object_id: ObjectId = Field(...)  # Store the original ObjectId from students collection
    
    # Original creation date
    created_at: datetime = Field(...)
    
    class Settings:
        name = "blacklist"
        indexes = [
            # Text index for name searching - enables fast text search on names
            IndexModel(
                [("first_name", TEXT), ("last_name", TEXT)],
                name="blacklist_name_text_index"
            ),
            # Individual name indexes for exact matching and regex searches
            IndexModel(
                [("first_name", ASCENDING)],
                name="blacklist_first_name_index"
            ),
            IndexModel(
                [("last_name", ASCENDING)],
                name="blacklist_last_name_index"
            ),
            # Phone number index - critical for blacklist checks during student creation
            IndexModel(
                [("phone_number", ASCENDING)],
                name="blacklist_phone_number_index"
            ),
            # Guardian number index
            IndexModel(
                [("guardian_number", ASCENDING)],
                name="blacklist_guardian_number_index"
            ),
            # Student ID index
            IndexModel(
                [("student_id", ASCENDING)],
                name="blacklist_student_id_index"
            ),
            # UID index
            IndexModel(
                [("uid", ASCENDING)],
                name="blacklist_uid_index"
            ),
            # Blacklist date index for chronological queries
            IndexModel(
                [("blacklisted_at", DESCENDING)],
                name="blacklist_date_index"
            ),
            # Level index for filtering
            IndexModel(
                [("level", ASCENDING)],
                name="blacklist_level_index"
            ),
            # Blacklist reason index for categorization
            IndexModel(
                [("blacklist_reason", ASCENDING)],
                name="blacklist_reason_index"
            ),
            # Original student object ID index for cross-referencing
            IndexModel(
                [("original_student_object_id", ASCENDING)],
                name="blacklist_original_id_index"
            ),
            # Compound index for phone and name checks (critical for duplicate prevention)
            IndexModel(
                [("phone_number", ASCENDING), ("first_name", ASCENDING), ("last_name", ASCENDING)],
                name="blacklist_phone_name_compound_index"
            ),
            # Compound index for level and name searches
            IndexModel(
                [("level", ASCENDING), ("first_name", ASCENDING), ("last_name", ASCENDING)],
                name="blacklist_level_name_compound_index"
            ),
            # Compound index for date and level
            IndexModel(
                [("blacklisted_at", DESCENDING), ("level", ASCENDING)],
                name="blacklist_date_level_compound_index"
            )
        ]
