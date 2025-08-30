from fastapi import APIRouter, HTTPException, Depends, Query
from bson import ObjectId
from typing import Optional
from app.database import db
from app.schemas.inventory import BookInventoryCreate, BookInventoryResponse, BookInventoryUpdate, PaginatedBooksResponse
from app.dependencies.auth import get_current_assistant

router = APIRouter(
    prefix="/inventory",
    tags=["Inventory"],
    dependencies=[Depends(get_current_assistant)]
)

collection = db["inventory"]

# Create book
@router.post("/", response_model=BookInventoryResponse)
async def create_book(book: BookInventoryCreate):
    existing = await collection.find_one({"name": book.name})
    if existing:
        raise HTTPException(status_code=400, detail="Book already exists")
    
    new_book = {
        "name": book.name,
        "quantity": book.quantity,
        "price": book.price,
        "level": book.level
    }
    result = await collection.insert_one(new_book)
    return BookInventoryResponse(
        id=str(result.inserted_id),
        **new_book
    )

# Get all books
@router.get("/", response_model=PaginatedBooksResponse)
async def get_all_books(
    page: int = Query(1, ge=1, description="Page number (starts from 1)"),
    limit: int = Query(25, ge=1, le=100, description="Number of items per page (max 100)"),
    q: Optional[str] = Query(None, description="Search query for book name"),
    level: Optional[int] = Query(None, ge=1, le=3, description="Filter by book level (1, 2, or 3)")
):
    """
    Get all books with optional search and filtering, plus pagination.
    
    Args:
        page: Page number (starts from 1)
        limit: Number of items per page (max 100)
        q: Optional search query for book name
        level: Optional filter by book level (1, 2, or 3)
    """
    # Build search and filter query using MongoDB syntax
    mongo_query = {}
    query_conditions = []
    
    # Add search functionality if q parameter is provided
    if q:
        # Search by book name (case-insensitive, partial match)
        query_conditions.append({"name": {"$regex": q, "$options": "i"}})
    
    # Add level filter if specified
    if level is not None:
        query_conditions.append({"level": level})
    
    # Combine all conditions
    if query_conditions:
        if len(query_conditions) > 1:
            mongo_query = {"$and": query_conditions}
        else:
            mongo_query = query_conditions[0]
    # If no conditions, mongo_query remains empty {}
    
    # Get total count with filters applied
    if mongo_query:
        total = await collection.count_documents(mongo_query)
    else:
        total = await collection.count_documents({})
    
    # Calculate skip from page number
    skip = (page - 1) * limit
    
    # Get books with pagination and filters (sorted by name)
    if mongo_query:
        cursor = collection.find(mongo_query).sort("name", 1).skip(skip).limit(limit)
    else:
        cursor = collection.find({}).sort("name", 1).skip(skip).limit(limit)
    
    books = []
    async for book in cursor:
        books.append(BookInventoryResponse(
            id=str(book["_id"]),
            name=book["name"],
            quantity=book["quantity"],
            price=book["price"],
            level=book.get("level", 1)  # Default to level 1 for existing books without level
        ))
    
    # Calculate pagination metadata
    total_pages = (total + limit - 1) // limit  # Ceiling division
    has_next = page < total_pages
    has_prev = page > 1
    
    return PaginatedBooksResponse(
        books=books,
        total=total,
        page=page,
        limit=limit,
        total_pages=total_pages,
        has_next=has_next,
        has_prev=has_prev
    )

# Update book
@router.put("/{book_id}", response_model=BookInventoryResponse)
async def update_book(book_id: str, book_update: BookInventoryUpdate):
    # Check if book exists
    existing_book = await collection.find_one({"_id": ObjectId(book_id)})
    if not existing_book:
        raise HTTPException(status_code=404, detail="Book not found")
    
    # Create update data (only include fields that are not None)
    update_data = {k: v for k, v in book_update.model_dump().items() if v is not None}
    
    if not update_data:
        raise HTTPException(status_code=400, detail="No data provided for update")
    
    # If updating name, check if new name already exists (but not for the same book)
    if "name" in update_data:
        name_exists = await collection.find_one({
            "name": update_data["name"], 
            "_id": {"$ne": ObjectId(book_id)}
        })
        if name_exists:
            raise HTTPException(status_code=400, detail="A book with this name already exists")
    
    # Update the book
    result = await collection.update_one(
        {"_id": ObjectId(book_id)}, 
        {"$set": update_data}
    )
    
    if result.modified_count == 0:
        raise HTTPException(status_code=400, detail="No changes made")
    
    # Get and return the updated book
    updated_book = await collection.find_one({"_id": ObjectId(book_id)})
    return BookInventoryResponse(
        id=str(updated_book["_id"]),
        name=updated_book["name"],
        quantity=updated_book["quantity"],
        price=updated_book["price"],
        level=updated_book.get("level", 1)
    )

# Delete book
@router.delete("/{book_id}")
async def delete_book(book_id: str):
    result = await collection.delete_one({"_id": ObjectId(book_id)})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Book not found")
    return {"message": "Book deleted successfully"}
