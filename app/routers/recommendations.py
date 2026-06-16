from fastapi import APIRouter, Depends, status

from app.dependencies import get_current_user
from app.schemas.recommendation_schema import ProductEvent, ProductEventCreate
from app.services import recommendation_service

router = APIRouter()


@router.post(
    "/events",
    response_model=ProductEvent,
    status_code=status.HTTP_201_CREATED,
)
def create_product_event(
    payload: ProductEventCreate,
    current_user: dict = Depends(get_current_user),
) -> dict:
    return recommendation_service.create_product_event(current_user["id"], payload)
