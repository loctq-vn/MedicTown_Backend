from fastapi import APIRouter, Depends

from app.dependencies import get_current_user
from app.schemas.review_schema import Review, ReviewCreate
from app.services import review_service

router = APIRouter()


@router.get("", response_model=list[Review])
def list_reviews(
    product_id: str | None = None,
    order_item_id: str | None = None,
) -> list[dict]:
    return review_service.list_reviews(
        product_id=product_id,
        order_item_id=order_item_id,
    )


@router.post("", response_model=Review)
def create_review(
    payload: ReviewCreate,
    current_user: dict = Depends(get_current_user),
) -> dict:
    return review_service.create_review(current_user["id"], payload)


@router.get("/products/{product_id}", response_model=list[Review])
def list_product_reviews(product_id: str) -> list[dict]:
    return review_service.list_product_reviews(product_id)
