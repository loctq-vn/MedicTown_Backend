from fastapi import HTTPException, status
from postgrest.exceptions import APIError

from app.database import supabase
from app.schemas.review_schema import ReviewCreate
from app.utils.postgrest_filters import parse_eq_filter, parse_in_filter


def _normalize_review(review: dict) -> dict:
    if review.get("images") is None:
        review["images"] = []
    return review


def create_review(user_id: str, payload: ReviewCreate) -> dict:
    if not payload.order_item_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="order_item_id is required",
        )

    order_item_response = (
        supabase.table("order_items")
        .select("id,order_id,product_id")
        .eq("id", payload.order_item_id)
        .maybe_single()
        .execute()
    )
    order_item = order_item_response.data
    if not order_item:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Order item not found",
        )
    if order_item["product_id"] != payload.product_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Review product does not match order item",
        )

    order_response = (
        supabase.table("orders")
        .select("id,user_id,status")
        .eq("id", order_item["order_id"])
        .eq("user_id", user_id)
        .maybe_single()
        .execute()
    )
    order = order_response.data
    if not order:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot review another user's order item",
        )
    if order.get("status") != "completed":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only completed orders can be reviewed",
        )

    existing_response = (
        supabase.table("reviews")
        .select("id")
        .eq("order_item_id", payload.order_item_id)
        .maybe_single()
        .execute()
    )
    if existing_response.data:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Order item already reviewed",
        )

    data = {
        "product_id": payload.product_id,
        "order_item_id": payload.order_item_id,
        "user_id": user_id,
        "rating": payload.rating,
        "comment": payload.comment,
    }
    if payload.images:
        data["images"] = payload.images

    try:
        response = supabase.table("reviews").insert(data).execute()
    except APIError as exc:
        if exc.args and isinstance(exc.args[0], dict) and exc.args[0].get("code") == "42703":
            data.pop("images", None)
            response = supabase.table("reviews").insert(data).execute()
        else:
            raise

    review = (response.data or [None])[0]
    if not review:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unable to create review",
        )
    return _normalize_review(review)


def list_product_reviews(product_id: str) -> list[dict]:
    return list_reviews(product_id=product_id)


def list_reviews(
    product_id: str | None = None,
    order_item_id: str | None = None,
) -> list[dict]:
    query = supabase.table("reviews").select("*,users(*)")

    if product_id:
        query = query.eq("product_id", parse_eq_filter(product_id))
    if order_item_id:
        order_item_ids = parse_in_filter(order_item_id)
        if order_item_ids:
            query = query.in_("order_item_id", order_item_ids)
        else:
            query = query.eq("order_item_id", parse_eq_filter(order_item_id))

    try:
        response = query.execute()
    except APIError as exc:
        if exc.args and isinstance(exc.args[0], dict) and exc.args[0].get("code") in {"PGRST200", "PGRST201"}:
            query = supabase.table("reviews").select("*")
            if product_id:
                query = query.eq("product_id", parse_eq_filter(product_id))
            if order_item_id:
                order_item_ids = parse_in_filter(order_item_id)
                if order_item_ids:
                    query = query.in_("order_item_id", order_item_ids)
                else:
                    query = query.eq("order_item_id", parse_eq_filter(order_item_id))
            response = query.execute()
        else:
            raise

    reviews = response.data or []
    for review in reviews:
        _normalize_review(review)
    return reviews
