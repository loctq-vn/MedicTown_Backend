from datetime import date
from typing import Literal

from fastapi import APIRouter, Depends, Query

from app.dependencies import get_current_user
from app.schemas.revenue_schema import (
    RevenueDailySummary,
    RevenueDashboard,
    RevenueTopProduct,
)
from app.services import revenue_service

router = APIRouter()


@router.get("/daily-summary", response_model=RevenueDailySummary)
def get_revenue_daily_summary(
    shop_id: str,
    from_date: date | None = Query(None, alias="from"),
    to_date: date | None = Query(None, alias="to"),
    current_user: dict = Depends(get_current_user),
) -> dict:
    return revenue_service.get_revenue_daily_summary(
        current_user["id"],
        shop_id,
        from_date,
        to_date,
    )


@router.get("/top-products", response_model=list[RevenueTopProduct])
def get_revenue_top_products(
    shop_id: str,
    from_date: date = Query(alias="from"),
    to_date: date = Query(alias="to"),
    current_user: dict = Depends(get_current_user),
) -> list[dict]:
    return revenue_service.get_revenue_top_products(
        current_user["id"],
        shop_id,
        from_date,
        to_date,
    )


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
