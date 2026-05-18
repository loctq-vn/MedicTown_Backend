from fastapi import APIRouter, Depends, status

from app.dependencies import get_current_user
from app.schemas.order_schema import OrderItem, OrderItemCreate
from app.services import order_service

router = APIRouter()


@router.post("", response_model=list[OrderItem], status_code=status.HTTP_201_CREATED)
def create_order_items(
    payload: list[OrderItemCreate],
    current_user: dict = Depends(get_current_user),
) -> list[dict]:
    data = [item.model_dump(exclude_none=True) for item in payload]
    return order_service.create_order_items(current_user["id"], data)
