from fastapi import APIRouter, Depends, Query, status

from app.dependencies import get_current_user
from app.schemas.recommendation_schema import (
    ProductEvent,
    ProductEventCreate,
    ProductRecommendation,
)
from app.services import recommendation_service

router = APIRouter()


@router.get("/me", response_model=list[ProductRecommendation])
def list_my_recommendations(
    limit: int = Query(default=20, ge=1, le=100),
    current_user: dict = Depends(get_current_user),
) -> list[dict]:
    return recommendation_service.list_user_recommendations(
        current_user["id"],
        limit=limit,
    )


@router.get("/products/{product_id}", response_model=list[ProductRecommendation])
def list_related_products(
    product_id: str,
    limit: int = Query(default=10, ge=1, le=100),
) -> list[dict]:
    return recommendation_service.list_related_products(product_id, limit=limit)


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
