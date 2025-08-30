from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import JSONResponse
from typing import List, Optional
from datetime import datetime
from bson import ObjectId
from beanie.operators import In
from collections import defaultdict
from calendar import month_name

from app.models.monthsale import MonthlySale
from app.models.booksale import BookSale
from app.models.counter import get_next_id
from app.schemas.monthsale import MonthlySaleCreate, MonthlySaleResponse, MonthQuery, MonthSaleDetailResponse, PaginatedMonthSalesResponse, SalesStatisticsResponse, MonthlySalesStats
from app.dependencies.auth import get_current_assistant
from app.models.student import StudentModel
from app.models.group import Group

router = APIRouter(prefix="/finance/monthsales", tags=["Finance"])


@router.post("/", response_model=MonthlySaleResponse)
async def create_month_sale(data: MonthlySaleCreate, assistant=Depends(get_current_assistant)):
    sale = MonthlySale(
        id=await get_next_id("monthsales"),
        student_id=ObjectId(data.student_id),
        price=data.price,
        default_price=data.default_price,
        month=data.month,
        created_at=datetime.utcnow()
    )
    await sale.insert()

    # ----------------------------
    # Update Student subscription
    # ----------------------------
    student = await StudentModel.get(sale.student_id)
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")

    # Initialize subscription and monthsales dicts if they don't exist
    if not student.subscription:
        student.subscription = {}

    student.subscription.setdefault("monthsales", {})

    # Format month key as "YYYY-MM"
    try:
        month_key = sale.month.strftime("%Y-%m")
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid month format")

    # Update the monthsales entry
    student.subscription["monthsales"][month_key] = float(sale.price)
    
    # Set is_subscription to True when a monthly sale is made
    student.is_subscription = True

    # Save the updated student
    await student.save()

    return MonthlySaleResponse(
        id=sale.id,
        student_id=str(sale.student_id),
        price=sale.price,
        default_price=sale.default_price,
        month=str(sale.month),
        created_at=sale.created_at,
    )


@router.delete("/{monthsale_id}")
async def delete_month_sale(monthsale_id: int, assistant=Depends(get_current_assistant)):
    sale = await MonthlySale.find_one(MonthlySale.id == monthsale_id)
    if not sale:
        raise HTTPException(status_code=404, detail="Month sale not found")
    await sale.delete()
    return {"detail": f"Month sale with id {monthsale_id} deleted successfully"}


@router.post("/by-month")
async def get_month_sales_by_month(
    data: MonthQuery,
    page: int = Query(1, ge=1, description="Page number (starts from 1)"),
    limit: int = Query(10, ge=1, le=100, description="Number of items per page (max 100)"),
    level: Optional[int] = Query(None, ge=1, le=3, description="Filter by student level (1, 2, or 3)"),
    group_name: Optional[str] = Query(None, description="Filter by group name"),
    assistant=Depends(get_current_assistant)
):
    """
    Get monthsales for a specific month with optional filtering by level and group.
    
    Args:
        data: MonthQuery containing the month in YYYY-MM format
        page: Page number (starts from 1)
        limit: Number of items per page (max 100)
        level: Optional filter by student level (1, 2, or 3)
        group_name: Optional filter by group name
    """
    try:
        # Parse the month string to create a datetime object for the specific month
        target_month = datetime.strptime(data.month, "%Y-%m")
        
        # Build student filters if level or group_name are provided
        student_ids = None
        if level is not None or group_name is not None:
            # Build filters for students
            student_filters = {}
            if level is not None:
                student_filters["level"] = level
            
            # Get filtered students
            if group_name:
                # Find group by name
                group = await Group.find_one(Group.group_name == group_name)
                if not group:
                    return {
                        "message": f"Group '{group_name}' not found", 
                        "monthsales": [],
                        "total_count": 0,
                        "page": page,
                        "limit": limit,
                        "total_pages": 0,
                        "has_next": False,
                        "has_prev": False,
                        "filters_applied": {"level": level, "group_name": group_name}
                    }
                
                # Get students in this group
                if student_filters:
                    students = await StudentModel.find(
                        In(StudentModel.id, group.students),
                        **student_filters
                    ).to_list()
                else:
                    students = await StudentModel.find(In(StudentModel.id, group.students)).to_list()
            else:
                # Get all students or filtered by level only
                if student_filters:
                    students = await StudentModel.find(student_filters).to_list()
                else:
                    students = await StudentModel.find_all().to_list()
            
            # Get student IDs for filtering sales
            student_ids = [student.id for student in students]
            
            if not student_ids:
                return {
                    "message": "No students found matching criteria",
                    "monthsales": [],
                    "total_count": 0,
                    "page": page,
                    "limit": limit,
                    "total_pages": 0,
                    "has_next": False,
                    "has_prev": False,
                    "filters_applied": {"level": level, "group_name": group_name}
                }

        # Build the query for monthsales using the month field (not created_at)
        # We need to match the exact year and month from the month field
        start_of_month = datetime(target_month.year, target_month.month, 1)
        if target_month.month == 12:
            start_of_next_month = datetime(target_month.year + 1, 1, 1)
        else:
            start_of_next_month = datetime(target_month.year, target_month.month + 1, 1)
        
        query_filter = {"month": {"$gte": start_of_month, "$lt": start_of_next_month}}
        
        # Get total count first (before pagination)
        if student_ids is not None:
            total_count = await MonthlySale.find(
                In(MonthlySale.student_id, student_ids),
                query_filter
            ).count()
        else:
            total_count = await MonthlySale.find(query_filter).count()
        
        # Calculate pagination
        skip = (page - 1) * limit
        total_pages = (total_count + limit - 1) // limit  # Ceiling division
        has_next = page < total_pages
        has_prev = page > 1
        
        # Add student filter and pagination
        if student_ids is not None:
            sales = await MonthlySale.find(
                In(MonthlySale.student_id, student_ids),
                query_filter
            ).skip(skip).limit(limit).to_list()
        else:
            # Query MongoDB using month field with pagination
            sales = await MonthlySale.find(query_filter).skip(skip).limit(limit).to_list()

        # Convert to response format
        result = [
            {
                "id": sale.id,
                "student_id": str(sale.student_id),
                "price": float(sale.price),
                "default_price": float(sale.default_price),
                "month": str(sale.month),
                "created_at": sale.created_at.isoformat()
            }
            for sale in sales
        ]

        return {
            "monthsales": result,
            "total_count": total_count,
            "page": page,
            "limit": limit,
            "total_pages": total_pages,
            "has_next": has_next,
            "has_prev": has_prev,
            "filters_applied": {
                "month": data.month,
                "level": level,
                "group_name": group_name,
                "students_found": len(student_ids) if student_ids is not None else "all"
            }
        }

    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid month format. Use YYYY-MM")


@router.get("/student/{student_id}")
async def get_monthsales_by_student(student_id: str, assistant=Depends(get_current_assistant)):
    try:
        student_obj_id = ObjectId(student_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid student ID")

    sales = await MonthlySale.find(MonthlySale.student_id == student_obj_id).to_list()

    total_price = sum(sale.price for sale in sales)

    monthly_sales = [
        {
            "id": sale.id,
            "student_id": str(sale.student_id),
            "price": sale.price,
            "default_price": sale.default_price,
            "month": str(sale.month),
            "created_at": sale.created_at,
        }
        for sale in sales
    ]

    return {
        "student_total_price": total_price,
        "monthly_sales": monthly_sales
    }

@router.get("/all", response_model=PaginatedMonthSalesResponse)
async def get_all_monthsales(page: int = 1, limit: int = 10, assistant=Depends(get_current_assistant)):
    # Get total count
    total = await MonthlySale.count()
    
    # Calculate skip from page number
    skip = (page - 1) * limit
    
    # Get monthsales with pagination
    monthsales = await MonthlySale.find_all().skip(skip).limit(limit).to_list()

    student_ids = list({sale.student_id for sale in monthsales})
    students = await StudentModel.find(In(StudentModel.id, student_ids)).to_list()
    
    student_map = {
        student.id: f"{student.first_name} {student.last_name}" for student in students
    }

    response = []
    for sale in monthsales:
        student_name = student_map.get(sale.student_id, "Unknown")
        sale_month = sale.created_at.strftime("%Y-%m")  # Extract the month

        response.append(MonthSaleDetailResponse(
            student_name=student_name,
            price=float(sale.price),
            created_at=sale.created_at,
            month=sale_month
        ))
    
    # Calculate pagination metadata
    total_pages = (total + limit - 1) // limit  # Ceiling division
    has_next = page < total_pages
    has_prev = page > 1

    return PaginatedMonthSalesResponse(
        month_sales=response,
        total=total,
        page=page,
        limit=limit,
        total_pages=total_pages,
        has_next=has_next,
        has_prev=has_prev
    )

@router.get("/statistics", response_model=SalesStatisticsResponse)
async def get_sales_statistics(
    level: Optional[int] = Query(None, ge=1, le=3, description="Filter by student level (1, 2, or 3)"),
    group_name: Optional[str] = Query(None, description="Filter by group name"),
    assistant=Depends(get_current_assistant)
):
    """
    Get statistics for monthsales and booksales by month with optional filtering by level and group.
    
    Args:
        level: Optional filter by student level (1, 2, or 3)
        group_name: Optional filter by group name
    
    Returns monthly statistics showing:
    - Number of students who made monthsales each month
    - Number of books sold each month
    - Total revenue for monthsales and booksales
    """
    # Build filters for students
    student_filters = {}
    if level is not None:
        student_filters["level"] = level
    
    # Get filtered students
    if group_name:
        # Find group by name
        group = await Group.find_one(Group.group_name == group_name)
        if not group:
            return SalesStatisticsResponse(
                statistics=[],
                total_months=0,
                filters_applied={"level": level, "group_name": group_name, "error": "Group not found"}
            )
        
        # Get students in this group
        if student_filters:
            students = await StudentModel.find(
                In(StudentModel.id, group.students),
                **student_filters
            ).to_list()
        else:
            students = await StudentModel.find(In(StudentModel.id, group.students)).to_list()
    else:
        # Get all students or filtered by level only
        if student_filters:
            students = await StudentModel.find(student_filters).to_list()
        else:
            students = await StudentModel.find_all().to_list()
    
    # Get student IDs for filtering sales
    student_ids = [student.id for student in students]
    
    if not student_ids:
        return SalesStatisticsResponse(
            statistics=[],
            total_months=0,
            filters_applied={"level": level, "group_name": group_name, "message": "No students found matching criteria"}
        )
    
    # Get all monthsales and booksales for filtered students
    monthsales = await MonthlySale.find(In(MonthlySale.student_id, student_ids)).to_list()
    booksales = await BookSale.find(In(BookSale.student_id, student_ids)).to_list()
    
    # Group data by month
    monthly_stats = defaultdict(lambda: {
        "monthsales_students": set(),
        "booksales_count": 0,
        "monthsales_revenue": 0.0,
        "booksales_revenue": 0.0
    })
    
    # Process monthsales - use sale.month instead of sale.created_at
    for sale in monthsales:
        month_key = sale.month.strftime("%Y-%m")  # Use the actual month field, not created_at
        monthly_stats[month_key]["monthsales_students"].add(sale.student_id)
        monthly_stats[month_key]["monthsales_revenue"] += float(sale.price)
    
    # Process booksales - use sale.created_at since booksales don't have a specific month field
    for sale in booksales:
        month_key = sale.created_at.strftime("%Y-%m")
        monthly_stats[month_key]["booksales_count"] += 1
        monthly_stats[month_key]["booksales_revenue"] += float(sale.price)
    
    # Convert to response format
    statistics = []
    for month_key in sorted(monthly_stats.keys()):
        stats = monthly_stats[month_key]
        
        # Parse month for display
        try:
            year, month = month_key.split('-')
            month_display = f"{month_name[int(month)]} {year}"
        except (ValueError, IndexError):
            month_display = month_key
        
        monthly_stat = MonthlySalesStats(
            month=month_key,
            month_name=month_display,
            monthsales_count=len(stats["monthsales_students"]),
            booksales_count=stats["booksales_count"],
            total_monthsales_revenue=round(stats["monthsales_revenue"], 2),
            total_booksales_revenue=round(stats["booksales_revenue"], 2),
            total_revenue=round(stats["monthsales_revenue"] + stats["booksales_revenue"], 2)
        )
        statistics.append(monthly_stat)
    
    return SalesStatisticsResponse(
        statistics=statistics,
        total_months=len(statistics),
        filters_applied={
            "level": level,
            "group_name": group_name,
            "students_found": len(student_ids)
        }
    )
