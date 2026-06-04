from datetime import date
from typing import Literal

from fastapi import APIRouter, Depends, Query

from app.dependencies import get_current_user
from app.schemas.revenue_schema import RevenueDashboard
from app.services import revenue_service

router = APIRouter()


@router.get("/dashboard", response_model=RevenueDashboard)
def get_revenue_dashboard(
    shop_id: str,
    from_date: date = Query(alias="from"),
    to_date: date = Query(alias="to"),
    group_by: Literal["day", "week", "month"] = Query("day", alias="groupBy"),
    current_user: dict = Depends(get_current_user),
) -> dict:
    return revenue_service.get_revenue_dashboard(
        current_user["id"],
        shop_id,
        from_date,
        to_date,
        group_by,
    )
