from app.database import supabase
from app.utils.postgrest_filters import parse_ilike_filter


def list_products(
    search: str | None = None,
    category_id: str | None = None,
    subcategory_id: str | None = None,
    shop_id: str | None = None,
    is_featured: bool | None = None,
    is_active: bool | None = None,
    limit: int = 20,
    offset: int = 0,
) -> dict:
    query = supabase.table("products").select("*", count="exact")

    if search:
        query = query.ilike("name", f"%{search}%")
    if shop_id:
        query = query.eq("shop_id", shop_id)
    if subcategory_id:
        query = query.eq("subcategory_id", subcategory_id)
    elif category_id:
        subcategories_response = (
            supabase.table("product_subcategories")
            .select("id")
            .eq("category_id", category_id)
            .eq("is_active", True)
            .execute()
        )
        subcategory_ids = [item["id"] for item in subcategories_response.data or []]
        if not subcategory_ids:
            return {"items": [], "total": 0}
        query = query.in_("subcategory_id", subcategory_ids)
    if is_featured is not None:
        query = query.eq("is_featured", is_featured)
    if is_active is not None:
        query = query.eq("is_active", is_active)

    response = query.range(offset, offset + limit - 1).execute()
    return {
        "items": response.data or [],
        "total": response.count or len(response.data or []),
    }


def list_categories() -> list[dict]:
    response = (
        supabase.table("product_categories")
        .select("*")
        .eq("is_active", True)
        .order("sort_order")
        .execute()
    )
    return response.data or []


def list_subcategories(category_id: str | None = None) -> list[dict]:
    query = (
        supabase.table("product_subcategories")
        .select("*")
        .eq("is_active", True)
        .order("sort_order")
    )
    if category_id:
        query = query.eq("category_id", category_id)
    response = query.execute()
    return response.data or []


def list_products_by_name_filter(
    name_filter: str | None = None,
    category_id: str | None = None,
    subcategory_id: str | None = None,
    shop_id: str | None = None,
    is_featured: bool | None = None,
    is_active: bool | None = None,
    limit: int = 20,
    offset: int = 0,
) -> dict:
    search_pattern = parse_ilike_filter(name_filter)
    query = supabase.table("products").select("*", count="exact")

    if search_pattern:
        query = query.ilike("name", search_pattern)
    if shop_id:
        query = query.eq("shop_id", shop_id)
    if subcategory_id:
        query = query.eq("subcategory_id", subcategory_id)
    elif category_id:
        subcategories_response = (
            supabase.table("product_subcategories")
            .select("id")
            .eq("category_id", category_id)
            .eq("is_active", True)
            .execute()
        )
        subcategory_ids = [item["id"] for item in subcategories_response.data or []]
        if not subcategory_ids:
            return {"items": [], "total": 0}
        query = query.in_("subcategory_id", subcategory_ids)
    if is_featured is not None:
        query = query.eq("is_featured", is_featured)
    if is_active is not None:
        query = query.eq("is_active", is_active)

    response = query.range(offset, offset + limit - 1).execute()
    return {
        "items": response.data or [],
        "total": response.count or len(response.data or []),
    }
