from fastapi import HTTPException, status

from app.database import supabase
from app.utils.postgrest_filters import parse_ilike_filter


def list_products(
    search: str | None = None,
    category_id: str | None = None,
    is_featured: bool | None = None,
    is_active: bool | None = None,
    limit: int = 20,
    offset: int = 0,
) -> dict:
    query = supabase.table("products").select("*", count="exact")

    if search:
        query = query.ilike("name", f"%{search}%")
    if category_id:
        query = query.eq("category_id", category_id)
    if is_featured is not None:
        query = query.eq("is_featured", is_featured)
    if is_active is not None:
        query = query.eq("is_active", is_active)

    response = query.range(offset, offset + limit - 1).execute()
    return {
        "items": response.data or [],
        "total": response.count or len(response.data or []),
    }


def list_products_by_name_filter(
    name_filter: str | None = None,
    is_featured: bool | None = None,
    is_active: bool | None = None,
    limit: int = 20,
    offset: int = 0,
) -> dict:
    search_pattern = parse_ilike_filter(name_filter)
    query = supabase.table("products").select("*", count="exact")

    if search_pattern:
        query = query.ilike("name", search_pattern)
    if is_featured is not None:
        query = query.eq("is_featured", is_featured)
    if is_active is not None:
        query = query.eq("is_active", is_active)

    response = query.range(offset, offset + limit - 1).execute()
    return {
        "items": response.data or [],
        "total": response.count or len(response.data or []),
    }


def get_product(product_id: str) -> dict:
    response = (
        supabase.table("products")
        .select("*")
        .eq("id", product_id)
        .maybe_single()
        .execute()
    )

    if not response.data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Product not found",
        )

    return response.data
