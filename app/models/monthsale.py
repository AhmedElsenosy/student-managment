from beanie import Document
from bson import ObjectId
from pydantic import Field
from datetime import datetime, date
from pymongo import IndexModel, ASCENDING, DESCENDING

class MonthlySale(Document):
    id: int
    student_id: ObjectId
    price: float
    default_price: float
    month: date
    created_at: datetime

    class Settings:
        name = "monthsales"
        indexes = [
            # Index on student_id for fast lookups when joining with students
            IndexModel(
                [("student_id", ASCENDING)],
                name="monthsales_student_id_index"
            ),
            # Index on created_at for sorting (most recent first)
            IndexModel(
                [("created_at", DESCENDING)],
                name="monthsales_created_at_index"
            ),
            # Index on month for filtering by specific months
            IndexModel(
                [("month", ASCENDING)],
                name="monthsales_month_index"
            ),
            # Compound index for efficient filtering and sorting
            IndexModel(
                [("created_at", DESCENDING), ("student_id", ASCENDING)],
                name="monthsales_date_student_compound_index"
            ),
            # Compound index for month and student filtering
            IndexModel(
                [("month", ASCENDING), ("student_id", ASCENDING)],
                name="monthsales_month_student_compound_index"
            )
        ]

    class Config:
        arbitrary_types_allowed = True
