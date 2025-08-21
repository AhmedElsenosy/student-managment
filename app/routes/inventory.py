from fastapi import APIRouter, HTTPException
from bson import ObjectId
from app.database import db
from app.schemas.inventory import BookInventoryCreate, BookInventoryResponse, BookInventoryUpdate

router = APIRouter(
    prefix="/inventory",
    tags=["Inventory"]
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
@router.get("/", response_model=list[BookInventoryResponse])
async def get_all_books():
    books = []
    async for book in collection.find():
        books.append(BookInventoryResponse(
            id=str(book["_id"]),
            name=book["name"],
            quantity=book["quantity"],
            price=book["price"],
            level=book.get("level", 1)  # Default to level 1 for existing books without level
        ))
    return books

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
