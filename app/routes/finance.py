from fastapi import APIRouter, Depends, HTTPException
from bson import ObjectId
from datetime import datetime, date
from decimal import Decimal
from collections import defaultdict
from pytz import timezone
from app.models.monthsale import MonthlySale
from app.models.booksale import BookSale
from app.models.outgoing import Outgoing
from app.schemas.profit import DailyProfitResponse, ProfitFilterRequest
from app.dependencies.auth import get_current_assistant

router = APIRouter(prefix="/finance", tags=["Finance"])
egypt_tz = timezone("Africa/Cairo")

@router.post("/profits", response_model=list[DailyProfitResponse])
async def get_daily_profits(
    filter_request: ProfitFilterRequest,
    assistant=Depends(get_current_assistant)
):
    profits_by_day = defaultdict(lambda: {
        "monthsales": Decimal("0.0"),
        "booksales": Decimal("0.0"),
        "outgoings": Decimal("0.0")
    })

    # Fetch all records
    monthsales = await MonthlySale.find_all().to_list()
    booksales = await BookSale.find_all().to_list()
    outgoings = await Outgoing.find_all().to_list()

    # Group and sum by Egypt day
    for sale in monthsales:
        local_day = sale.created_at.astimezone(egypt_tz).date()
        profits_by_day[local_day]["monthsales"] += Decimal(str(sale.price))

    for sale in booksales:
        local_day = sale.created_at.astimezone(egypt_tz).date()
        profits_by_day[local_day]["booksales"] += Decimal(str(sale.price))

    for out in outgoings:
        local_day = out.created_at.astimezone(egypt_tz).date()
        profits_by_day[local_day]["outgoings"] += Decimal(str(out.price))

    # Filter by date if provided
    result = []
    for day, values in sorted(profits_by_day.items()):
        if filter_request.day_date and day != filter_request.day_date:
            continue

        profit = (values["monthsales"] + values["booksales"]) - values["outgoings"]
        result.append(DailyProfitResponse(
            date=day,
            total_monthsales=values["monthsales"],
            total_booksales=values["booksales"],
            total_outgoings=values["outgoings"],
            profit=profit
        ))

    return result


@router.get("/booksales/last-default-price/{student_id}")
async def get_last_default_price(student_id: str, assistant=Depends(get_current_assistant)):
    if not ObjectId.is_valid(student_id):
        raise HTTPException(status_code=400, detail="Invalid student ID")

    # Fetch the latest book sale for the student by created_at descending
    last_sale = await BookSale.find(
        BookSale.student_id == ObjectId(student_id)
    ).sort("-created_at").first_or_none()

    if not last_sale:
        raise HTTPException(status_code=404, detail="No book sales found for this student")

    return {
        "student_id": student_id,
        "last_default_price": last_sale.default_price
    }

@router.get("/monthsales/last-default-price/{student_id}")
async def get_last_month_default_price(student_id: str, assistant=Depends(get_current_assistant)):
    if not ObjectId.is_valid(student_id):
        raise HTTPException(status_code=400, detail="Invalid student ID")

    last_month_sale = await MonthlySale.find(
        MonthlySale.student_id == ObjectId(student_id)
    ).sort("-created_at").first_or_none()

    if not last_month_sale:
        raise HTTPException(status_code=404, detail="No monthly sales found for this student")

    return {
        "student_id": student_id,
        "last_default_price": last_month_sale.default_price
    }


@router.get("/monthly-summary")
async def get_monthly_summary(assistant=Depends(get_current_assistant)):
    monthsales = await MonthlySale.find_all().to_list()
    booksales = await BookSale.find_all().to_list()

    report = defaultdict(lambda: {
        "student_ids": set(),
        "total_monthsales_price": 0,
        "total_booksales_price": 0,
        "books_sold_count": 0,
    })

    # Process monthsales
    for sale in monthsales:
        # Ensure month is in "YYYY-MM" format
        if isinstance(sale.month, str):
            month = sale.month
        elif isinstance(sale.month, datetime):
            month = sale.month.strftime("%Y-%m")
        else:
            # If it's a date or invalid, convert it
            try:
                month = sale.month.strftime("%Y-%m")
            except Exception:
                raise ValueError(f"Invalid month value: {sale.month}")

        report[month]["student_ids"].add(str(sale.student_id))
        report[month]["total_monthsales_price"] += float(sale.price)

    # Process booksales
    for sale in booksales:
        month = sale.created_at.strftime("%Y-%m")
        report[month]["total_booksales_price"] += float(sale.price)
        report[month]["books_sold_count"] += 1

    # Build response
    final_report = []
    for month, data in sorted(report.items()):
        final_report.append({
            "month": month,
            "student_count": len(data["student_ids"]),
            "total_monthsales_price": round(data["total_monthsales_price"], 2),
            "total_booksales_price": round(data["total_booksales_price"], 2),
            "books_sold_count": data["books_sold_count"]
        })

    return final_report


@router.get("/dashboard")
async def get_financial_dashboard(assistant=Depends(get_current_assistant)):
    """
    Comprehensive financial dashboard showing:
    - Total income from monthsales and booksales
    - Total outgoings/expenses
    - Net profit (income - expenses)
    - Profit percentage
    - Breakdown by category
    """
    try:
        # Fetch all financial data
        monthsales = await MonthlySale.find_all().to_list()
        booksales = await BookSale.find_all().to_list()
        outgoings = await Outgoing.find_all().to_list()
        
        # Calculate totals
        total_monthsales = sum(float(sale.price) for sale in monthsales)
        total_booksales = sum(float(sale.price) for sale in booksales)
        total_outgoings = sum(float(expense.price) for expense in outgoings)
        
        # Calculate derived metrics
        total_income = total_monthsales + total_booksales
        net_profit = total_income - total_outgoings
        
        # Calculate profit percentage (profit margin)
        profit_percentage = (net_profit / total_income * 100) if total_income > 0 else 0
        
        # Calculate expense ratio
        expense_ratio = (total_outgoings / total_income * 100) if total_income > 0 else 0
        
        # Count records for additional insights
        monthsales_count = len(monthsales)
        booksales_count = len(booksales)
        outgoings_count = len(outgoings)
        
        # Calculate averages
        avg_monthsale = total_monthsales / monthsales_count if monthsales_count > 0 else 0
        avg_booksale = total_booksales / booksales_count if booksales_count > 0 else 0
        avg_outgoing = total_outgoings / outgoings_count if outgoings_count > 0 else 0
        
        # Get unique students count
        unique_students_monthsales = len(set(str(sale.student_id) for sale in monthsales))
        unique_students_booksales = len(set(str(sale.student_id) for sale in booksales))
        total_unique_students = len(set(
            list(str(sale.student_id) for sale in monthsales) +
            list(str(sale.student_id) for sale in booksales)
        ))
        
        return {
            "success": True,
            "summary": {
                "total_income": round(total_income, 2),
                "total_outgoings": round(total_outgoings, 2),
                "net_profit": round(net_profit, 2),
                "profit_percentage": round(profit_percentage, 2),
                "expense_ratio": round(expense_ratio, 2)
            },
            "income_breakdown": {
                "monthsales": {
                    "total": round(total_monthsales, 2),
                    "count": monthsales_count,
                    "average": round(avg_monthsale, 2),
                    "unique_students": unique_students_monthsales,
                    "percentage_of_income": round((total_monthsales / total_income * 100) if total_income > 0 else 0, 2)
                },
                "booksales": {
                    "total": round(total_booksales, 2),
                    "count": booksales_count,
                    "average": round(avg_booksale, 2),
                    "unique_students": unique_students_booksales,
                    "percentage_of_income": round((total_booksales / total_income * 100) if total_income > 0 else 0, 2)
                }
            },
            "expenses_breakdown": {
                "outgoings": {
                    "total": round(total_outgoings, 2),
                    "count": outgoings_count,
                    "average": round(avg_outgoing, 2),
                    "percentage_of_income": round(expense_ratio, 2)
                }
            },
            "student_metrics": {
                "total_unique_students": total_unique_students,
                "monthsales_students": unique_students_monthsales,
                "booksales_students": unique_students_booksales,
                "revenue_per_student": round(total_income / total_unique_students, 2) if total_unique_students > 0 else 0
            },
            "performance_indicators": {
                "is_profitable": net_profit > 0,
                "profitability_status": "Profitable" if net_profit > 0 else "Loss" if net_profit < 0 else "Break-even",
                "financial_health": (
                    "Excellent" if profit_percentage >= 30 else
                    "Good" if profit_percentage >= 20 else
                    "Fair" if profit_percentage >= 10 else
                    "Poor" if profit_percentage >= 0 else
                    "Critical"
                ),
                "expense_efficiency": (
                    "Excellent" if expense_ratio <= 30 else
                    "Good" if expense_ratio <= 50 else
                    "Fair" if expense_ratio <= 70 else
                    "Poor"
                )
            },
            "timestamp": datetime.utcnow().isoformat(),
            "currency": "EGP"  # Assuming Egyptian Pounds
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error calculating financial dashboard: {str(e)}")


@router.get("/subscription")
async def get_subscription_metrics(
    level: int = None,
    group_name: str = None,
    assistant=Depends(get_current_assistant)
):
    """
    Subscription-focused metrics showing:
    - Number of monthsales (all time)
    - Active subscriptions count (students with is_subscription = true)
    - Number of booksales (all time)
    - Total money from monthsales and booksales
    - Percentage breakdown of income sources
    
    Args:
        level: Optional filter by student level (1, 2, or 3)
        group_name: Optional filter by group name
    """
    try:
        from app.database import db
        from app.models.group import Group
        from beanie.operators import In
        
        # Build student filters
        student_filters = {}
        filtered_student_ids = None
        
        # Apply level filter
        if level is not None:
            student_filters["level"] = level
        
        # Apply group filter
        if group_name:
            # Find group by name
            group = await Group.find_one(Group.group_name == group_name)
            if group:
                filtered_student_ids = group.students
            else:
                # Group not found, return empty result
                return {
                    "success": False,
                    "message": f"Group '{group_name}' not found",
                    "filters_applied": {"level": level, "group_name": group_name},
                    "subscription_overview": {"active_subscriptions": 0, "total_students": 0},
                    "sales_summary": {"monthsales": {"count": 0, "revenue": 0}, "booksales": {"count": 0, "revenue": 0}}
                }
        
        # Get filtered students
        students_collection = db["students"]
        
        if filtered_student_ids is not None:
            # Filter by both group and level (if provided)
            if student_filters:
                student_query = {"_id": {"$in": filtered_student_ids}, **student_filters}
            else:
                student_query = {"_id": {"$in": filtered_student_ids}}
        else:
            # Filter by level only (if provided)
            student_query = student_filters if student_filters else {}
        
        # Get filtered students
        filtered_students = await students_collection.find(student_query).to_list(length=None)
        filtered_student_object_ids = [student["_id"] for student in filtered_students]
        
        # Count active subscriptions in filtered students
        active_subscriptions_query = {**student_query, "is_subscription": True}
        active_subscriptions = await students_collection.count_documents(active_subscriptions_query)
        total_students = len(filtered_students)
        
        # Filter monthsales and booksales by student IDs
        if filtered_student_object_ids:
            monthsales = await MonthlySale.find(In(MonthlySale.student_id, filtered_student_object_ids)).to_list()
            booksales = await BookSale.find(In(BookSale.student_id, filtered_student_object_ids)).to_list()
        else:
            # No students found matching criteria
            monthsales = []
            booksales = []
        
        # Calculate totals
        total_monthsales_count = len(monthsales)
        total_booksales_count = len(booksales)
        total_monthsales_revenue = sum(float(sale.price) for sale in monthsales)
        total_booksales_revenue = sum(float(sale.price) for sale in booksales)
        
        # Calculate total revenue and percentages
        total_revenue = total_monthsales_revenue + total_booksales_revenue
        monthsales_percentage = (total_monthsales_revenue / total_revenue * 100) if total_revenue > 0 else 0
        booksales_percentage = (total_booksales_revenue / total_revenue * 100) if total_revenue > 0 else 0
        
        # Calculate subscription rate
        subscription_rate = (active_subscriptions / total_students * 100) if total_students > 0 else 0
        
        # Get unique students from sales
        unique_monthsales_students = len(set(str(sale.student_id) for sale in monthsales))
        unique_booksales_students = len(set(str(sale.student_id) for sale in booksales))
        
        # Calculate averages
        avg_monthsale_value = total_monthsales_revenue / total_monthsales_count if total_monthsales_count > 0 else 0
        avg_booksale_value = total_booksales_revenue / total_booksales_count if total_booksales_count > 0 else 0
        
        # Revenue per active subscriber
        revenue_per_subscriber = total_revenue / active_subscriptions if active_subscriptions > 0 else 0
        
        return {
            "success": True,
            "subscription_overview": {
                "active_subscriptions": active_subscriptions,
                "total_students": total_students,
                "subscription_rate_percentage": round(subscription_rate, 2),
                "inactive_subscriptions": total_students - active_subscriptions
            },
            "sales_summary": {
                "monthsales": {
                    "count": total_monthsales_count,
                    "revenue": round(total_monthsales_revenue, 2),
                    "percentage_of_total_revenue": round(monthsales_percentage, 2),
                    "average_value": round(avg_monthsale_value, 2),
                    "unique_students": unique_monthsales_students
                },
                "booksales": {
                    "count": total_booksales_count,
                    "revenue": round(total_booksales_revenue, 2),
                    "percentage_of_total_revenue": round(booksales_percentage, 2),
                    "average_value": round(avg_booksale_value, 2),
                    "unique_students": unique_booksales_students
                }
            },
            "revenue_summary": {
                "total_revenue": round(total_revenue, 2),
                "monthsales_revenue": round(total_monthsales_revenue, 2),
                "booksales_revenue": round(total_booksales_revenue, 2),
                "monthsales_percentage": round(monthsales_percentage, 2),
                "booksales_percentage": round(booksales_percentage, 2)
            },
            "performance_metrics": {
                "revenue_per_subscriber": round(revenue_per_subscriber, 2),
                "monthsales_per_subscriber": round(total_monthsales_revenue / active_subscriptions, 2) if active_subscriptions > 0 else 0,
                "booksales_per_subscriber": round(total_booksales_revenue / active_subscriptions, 2) if active_subscriptions > 0 else 0,
                "average_transactions_per_subscriber": round((total_monthsales_count + total_booksales_count) / active_subscriptions, 2) if active_subscriptions > 0 else 0
            },
            "insights": {
                "primary_revenue_source": "Monthsales" if monthsales_percentage > booksales_percentage else "Booksales",
                "subscription_health": (
                    "Excellent" if subscription_rate >= 80 else
                    "Good" if subscription_rate >= 60 else
                    "Fair" if subscription_rate >= 40 else
                    "Poor" if subscription_rate >= 20 else
                    "Critical"
                ),
                "revenue_diversification": (
                    "Balanced" if abs(monthsales_percentage - booksales_percentage) <= 20 else
                    "Monthsales-Heavy" if monthsales_percentage > booksales_percentage else
                    "Booksales-Heavy"
                )
            },
            "filters_applied": {
                "level": level,
                "group_name": group_name,
                "students_found": total_students
            },
            "timestamp": datetime.utcnow().isoformat(),
            "currency": "EGP"
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error calculating subscription metrics: {str(e)}")
