from fastapi import HTTPException, status

from app.database import supabase
from app.schemas.recommendation_schema import ProductEventCreate


def create_product_event(user_id: str, payload: ProductEventCreate) -> dict:
    _ensure_product_exists(payload.product_id)

    response = (
        supabase.table("product_events")
        .insert(
            {
                "user_id": user_id,
                "product_id": payload.product_id,
                "event_type": payload.event_type,
                "metadata": payload.metadata or {},
            }
        )
        .execute()
    )
    event = (response.data or [None])[0]
    if not event:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unable to record product event",
        )
    return event


def _ensure_product_exists(product_id: str) -> None:
    response = (
        supabase.table("products")
        .select("id")
        .eq("id", product_id)
        .maybe_single()
        .execute()
    )
    if not response.data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Product not found",
        )
