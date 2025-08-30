from fastapi import APIRouter, Query
from datetime import datetime, date
from typing import Optional
from app.models.outgoing import Outgoing
from app.schemas.outgoing import OutgoingCreate, OutgoingResponse, PaginatedOutgoingsResponse
from app.models.counter import get_next_id
from fastapi import HTTPException, Depends
from app.dependencies.auth import get_current_assistant


router = APIRouter(prefix="/finance/outgoings", tags=["Outgoings"])

@router.post("/", response_model=OutgoingResponse)
async def create_outgoing(data: OutgoingCreate, assistant=Depends(get_current_assistant)):
    outgoing = Outgoing(
        id=await get_next_id("outgoings"),
        product_name=data.product_name,
        price=data.price,
        created_at=datetime.utcnow()
    )
    await outgoing.insert()
    return outgoing

@router.get("/", response_model=PaginatedOutgoingsResponse)
async def get_all_outgoings(
    page: int = Query(1, ge=1, description="Page number (starts from 1)"),
    limit: int = Query(30, ge=1, le=100, description="Number of items per page (max 100)"),
    q: Optional[str] = Query(None, description="Search query for product name"),
    created_at: Optional[date] = Query(None, description="Filter outgoings by specific date (YYYY-MM-DD)"),
    assistant=Depends(get_current_assistant)
):
    """
    Get all outgoings with optional search and date filtering, plus pagination.
    
    Args:
        page: Page number (starts from 1)
        limit: Number of items per page (max 100)
        q: Optional search query for product name
        created_at: Optional filter by specific date (YYYY-MM-DD) - shows all outgoings created on this date
    """
    # Build search and filter query using MongoDB syntax
    mongo_query = {}
    query_conditions = []
    
    # Add search functionality if q parameter is provided
    if q:
        # Search by product name (case-insensitive, partial match)
        query_conditions.append({"product_name": {"$regex": q, "$options": "i"}})
    
    # Add date filtering if provided - filter by specific date (entire day)
    if created_at:
        # Filter for the entire day: from start of day (00:00:00) to end of day (23:59:59)
        start_of_day = datetime.combine(created_at, datetime.min.time())
        end_of_day = datetime.combine(created_at, datetime.max.time())
        
        date_filter = {
            "$gte": start_of_day,
            "$lte": end_of_day
        }
        
        query_conditions.append({"created_at": date_filter})
    
    # Combine all conditions
    if query_conditions:
        if len(query_conditions) > 1:
            mongo_query = {"$and": query_conditions}
        else:
            mongo_query = query_conditions[0]
    # If no conditions, mongo_query remains empty {}
    
    # Get total count with filters applied
    if mongo_query:
        total = await Outgoing.find(mongo_query).count()
    else:
        total = await Outgoing.count()
    
    # Calculate skip from page number
    skip = (page - 1) * limit
    
    # Get outgoings with pagination and filters (newest first by created_at)
    if mongo_query:
        outgoings_data = await Outgoing.find(mongo_query).sort(["-created_at"]).skip(skip).limit(limit).to_list()
    else:
        outgoings_data = await Outgoing.find_all().sort(["-created_at"]).skip(skip).limit(limit).to_list()
    
    # Convert model objects to OutgoingResponse objects
    outgoings = [
        OutgoingResponse(
            id=outgoing.id,
            product_name=outgoing.product_name,
            price=outgoing.price,
            created_at=outgoing.created_at
        )
        for outgoing in outgoings_data
    ]
    
    # Calculate pagination metadata
    total_pages = (total + limit - 1) // limit  # Ceiling division
    has_next = page < total_pages
    has_prev = page > 1
    
    return PaginatedOutgoingsResponse(
        outgoings=outgoings,
        total=total,
        page=page,
        limit=limit,
        total_pages=total_pages,
        has_next=has_next,
        has_prev=has_prev
    )


@router.delete("/{id}")
async def delete_outgoing(id: int, assistant=Depends(get_current_assistant)):
    outgoing = await Outgoing.find_one(Outgoing.id == id)
    if not outgoing:
        raise HTTPException(status_code=404, detail="Outgoing not found")
    await outgoing.delete()
    return {"message": "Outgoing deleted successfully"}
