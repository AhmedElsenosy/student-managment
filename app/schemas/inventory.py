from pydantic import BaseModel, Field
from typing import Optional, List

class BookInventoryCreate(BaseModel):
    name: str
    quantity: int
    price: float
    level: int = Field(..., ge=1, le=3)

class BookInventoryUpdate(BaseModel):
    name: Optional[str] = None
    quantity: Optional[int] = None
    price: Optional[float] = None
    level: Optional[int] = Field(None, ge=1, le=3)

class BookInventoryResponse(BaseModel):
    id: str
    name: str
    quantity: int
    price: float
    level: int

class PaginatedBooksResponse(BaseModel):
    books: List[BookInventoryResponse]
    total: int
    page: int
    limit: int
    total_pages: int
    has_next: bool
    has_prev: bool
