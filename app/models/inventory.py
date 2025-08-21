from pydantic import BaseModel, Field
from typing import Optional
from bson import ObjectId

class BookInventoryModel(BaseModel):
    id: Optional[str]
    name: str
    quantity: int
    price: float
    level: int = Field(..., ge=1, le=3)

    class Config:
        schema_extra = {
            "example": {
                "name": "Physics Book",
                "quantity": 20,
                "price": 150.0,
                "level": 1
            }
        }
