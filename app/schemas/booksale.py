from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime
from decimal import Decimal

class BookSaleCreate(BaseModel):
    student_id: str  
    name: str
    price: Decimal
    default_price: Decimal

class BookSaleResponse(BaseModel):
    id: int
    student_id: str
    name: str
    price: Decimal
    default_price: Decimal
    created_at: datetime

class MonthQuery(BaseModel):
    month: str 

class BookSaleMonthSummary(BaseModel):
    month: int
    total_price: float


class BookSaleDetailResponse(BaseModel):
    student_name: str
    book_name: str
    price: float
    created_at: datetime

class PaginatedBookSalesResponse(BaseModel):
    book_sales: List[BookSaleDetailResponse]
    total: int
    page: int
    limit: int
    total_pages: int
    has_next: bool
    has_prev: bool

class BookSaleMonthlyStats(BaseModel):
    """Response model for monthly booksales statistics"""
    month: str
    month_name: str
    booksales_count: int
    total_revenue: float
    books: List[dict]  # List of books sold with their details

class FilteredBookSalesResponse(BaseModel):
    """Response model for filtered booksales by month"""
    monthly_stats: List[BookSaleMonthlyStats]
    total_months: int
    filters_applied: dict
