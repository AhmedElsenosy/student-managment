from beanie import Document
from bson import ObjectId, Decimal128
from decimal import Decimal
from datetime import datetime
from pydantic import Field, field_validator
from pymongo import IndexModel, ASCENDING, DESCENDING, TEXT


class BookSale(Document):
    id: int = Field(alias="_id")
    student_id: ObjectId
    name: str
    price: Decimal
    default_price: Decimal
    created_at: datetime

    class Settings:
        name = "booksales"
        indexes = [
            # Index on student_id for fast lookups when joining with students
            IndexModel(
                [("student_id", ASCENDING)],
                name="booksales_student_id_index"
            ),
            # Index on created_at for sorting (most recent first)
            IndexModel(
                [("created_at", DESCENDING)],
                name="booksales_created_at_index"
            ),
            # Index on book name for exact matching and sorting
            IndexModel(
                [("name", ASCENDING)],
                name="booksales_name_index"
            ),
            # Text index on book name for text searches
            IndexModel(
                [("name", TEXT)],
                name="booksales_name_text_index"
            ),
            # Compound index for efficient filtering and sorting
            IndexModel(
                [("created_at", DESCENDING), ("student_id", ASCENDING)],
                name="booksales_date_student_compound_index"
            ),
            # Compound index for book name and student filtering
            IndexModel(
                [("name", ASCENDING), ("student_id", ASCENDING)],
                name="booksales_name_student_compound_index"
            )
        ]

    model_config = {
        "arbitrary_types_allowed": True
    }

    @field_validator("price", "default_price", mode="before")
    @classmethod
    def convert_decimal128(cls, value):
        if isinstance(value, Decimal128):
            return value.to_decimal()
        return value
