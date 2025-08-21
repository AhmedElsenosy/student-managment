from fastapi import APIRouter, Depends, HTTPException, Body
from fastapi.encoders import jsonable_encoder
from datetime import datetime
from app.models.booksale import BookSale
from bson import ObjectId
from app.models.booksale import BookSale
from app.models.student import StudentModel
from app.models.counter import get_next_id
from app.schemas.booksale import BookSaleCreate, BookSaleResponse, MonthQuery, BookSaleMonthSummary, BookSaleDetailResponse, PaginatedBookSalesResponse
from app.dependencies.auth import get_current_assistant
from bson.decimal128 import Decimal128
from decimal import Decimal
from beanie import PydanticObjectId
from beanie.operators import In
from collections import defaultdict
from typing import List
from app.database import db


router = APIRouter(prefix="/finance/booksales", tags=["Finance"])

@router.post("/", response_model=BookSaleResponse)
async def create_book_sale(data: BookSaleCreate, assistant=Depends(get_current_assistant)):
    # ----------------------------
    # Validate inventory
    # ----------------------------
    inventory_collection = db["inventory"]
    
    # Check if book exists in inventory
    book_inventory = await inventory_collection.find_one({"name": data.name})
    if not book_inventory:
        raise HTTPException(
            status_code=400, 
            detail=f"Book '{data.name}' not found in inventory"
        )
    
    # Check if there's enough quantity (assuming 1 book per sale)
    if book_inventory["quantity"] < 1:
        raise HTTPException(
            status_code=400, 
            detail=f"Insufficient quantity for book '{data.name}'. Available: {book_inventory['quantity']}"
        )
    
    # Create the book sale
    sale = BookSale(
        id=await get_next_id("booksales"),
        student_id=ObjectId(data.student_id),
        price=data.price,
        default_price=data.default_price,
        name=data.name,  # use 'name' instead of 'book_name'
        created_at=datetime.utcnow()
    )
    await sale.insert()
    
    # ----------------------------
    # Update inventory quantity
    # ----------------------------
    await inventory_collection.update_one(
        {"name": data.name},
        {"$inc": {"quantity": -1}}  # Decrease quantity by 1
    )

    # ----------------------------
    # Update Student subscription
    # ----------------------------
    student = await StudentModel.get(sale.student_id)
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")

    # Ensure subscription.booksales exists
    if not student.subscription:
        student.subscription = {}
    if "booksales" not in student.subscription:
        student.subscription["booksales"] = {}

    # Use the book's name as key and price as value
    student.subscription["booksales"][sale.name] = float(sale.price)

    # Save the updated student
    await student.save()

    return BookSaleResponse(
        id=sale.id,
        student_id=str(sale.student_id),
        price=sale.price,
        default_price=sale.default_price,
        name=sale.name,
        created_at=sale.created_at,
    )



@router.delete("/{id}")
async def delete_booksale(id: int, assistant=Depends(get_current_assistant)):
    book_sale_doc = await BookSale.find_one(BookSale.id == id)  # works now
    if not book_sale_doc:
        raise HTTPException(status_code=404, detail=f"BookSale with id {id} not found")
    
    # Store book name before deletion for inventory restoration
    book_name = book_sale_doc.name
    
    # Delete the book sale
    await book_sale_doc.delete()
    
    # ----------------------------
    # Restore inventory quantity
    # ----------------------------
    inventory_collection = db["inventory"]
    
    # Check if book still exists in inventory (in case it was deleted)
    book_inventory = await inventory_collection.find_one({"name": book_name})
    if book_inventory:
        # Restore the quantity by adding 1 back
        await inventory_collection.update_one(
            {"name": book_name},
            {"$inc": {"quantity": 1}}  # Increase quantity by 1
        )
    
    return {"message": f"BookSale with id {id} deleted successfully and inventory restored"}


@router.post("/by-month")
async def get_booksales_by_month(query: MonthQuery, assistant=Depends(get_current_assistant)):
    try:
        # Parse month string into datetime
        month_start = datetime.strptime(query.month, "%Y-%m")
        # Get the first day of the next month
        if month_start.month == 12:
            next_month = datetime(month_start.year + 1, 1, 1)
        else:
            next_month = datetime(month_start.year, month_start.month + 1, 1)

        # Query MongoDB using date range
        booksales = await BookSale.find(
            {"created_at": {"$gte": month_start, "$lt": next_month}}
        ).to_list()

        # Convert ObjectIds to strings for JSON serialization
        for sale in booksales:
            sale.id = str(sale.id)
            sale.student_id = str(sale.student_id)

        return booksales

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    

@router.get("/student/{student_id}", response_model=list[dict])
async def get_booksales_by_month(student_id: str, assistant=Depends(get_current_assistant)):
    try:
        student_obj_id = ObjectId(student_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid student ID")

    sales = await BookSale.find(BookSale.student_id == student_obj_id).to_list()

    monthly_data = defaultdict(lambda: {"books": [], "total_price": 0.0})

    for sale in sales:
        # Format month as "YYYY-MM"
        month_key = sale.created_at.strftime("%Y-%m")
        monthly_data[month_key]["books"].append({
            "name": sale.name,
            "price": float(sale.price)
        })
        monthly_data[month_key]["total_price"] += float(sale.price)

    # Convert to list
    result = []
    for month, data in sorted(monthly_data.items()):
        result.append({
            "month": month,
            "books": data["books"],
            "total_price": round(data["total_price"], 2)
        })

    return result

@router.get("/all", response_model=PaginatedBookSalesResponse)
async def get_all_booksales(page: int = 1, limit: int = 10, assistant=Depends(get_current_assistant)):
    # Get total count
    total = await BookSale.count()
    
    # Calculate skip from page number
    skip = (page - 1) * limit
    
    # Get booksales with pagination
    booksales = await BookSale.find_all().skip(skip).limit(limit).to_list()

    # Get all student IDs
    student_ids = list({sale.student_id for sale in booksales})

    # Fetch related students
    students = await StudentModel.find(In(StudentModel.id, student_ids)).to_list()
    student_map = {s.id: f"{s.first_name} {s.last_name}" for s in students}

    response = []
    for sale in booksales:
        student_name = student_map.get(sale.student_id, "Unknown")
        response.append(BookSaleDetailResponse(
            student_name=student_name,
            book_name=getattr(sale, "name", "Unknown"),
            price=float(sale.price),
            created_at=sale.created_at
        ))
    
    # Calculate pagination metadata
    total_pages = (total + limit - 1) // limit  # Ceiling division
    has_next = page < total_pages
    has_prev = page > 1

    return PaginatedBookSalesResponse(
        book_sales=response,
        total=total,
        page=page,
        limit=limit,
        total_pages=total_pages,
        has_next=has_next,
        has_prev=has_prev
    )


