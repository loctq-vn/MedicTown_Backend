from fastapi import APIRouter, Depends

from app.dependencies import get_current_user
from app.schemas.order_schema import Order, OrderCreate
from app.services import order_service

router = APIRouter()


@router.post("", response_model=list[Order])
def create_order(
    payload: OrderCreate,
    current_user: dict = Depends(get_current_user),
) -> list[dict]:
    return [order_service.create_order(current_user["id"], payload)]


@router.get("", response_model=list[Order])
def list_orders(current_user: dict = Depends(get_current_user)) -> list[dict]:
    return order_service.list_orders(current_user["id"])


@router.get("/{order_id}", response_model=Order)
def get_order(
    order_id: str,
    current_user: dict = Depends(get_current_user),
) -> dict:
    return order_service.get_order(current_user["id"], order_id)
