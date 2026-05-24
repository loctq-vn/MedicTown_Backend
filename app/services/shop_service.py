from fastapi import HTTPException, status

from app.database import supabase
from app.schemas.product_schema import ProductCreate, ProductUpdate
from app.schemas.shop_schema import ShopCreate, ShopUpdate


def list_my_shops(user_id: str) -> list[dict]:
    response = (
        supabase.table("shops")
        .select("*")
        .eq("owner_id", user_id)
        .eq("is_active", True)
        .order("created_at", desc=True)
        .execute()
    )
    return response.data or []


def create_shop(user_id: str, payload: ShopCreate) -> dict:
    data = payload.model_dump(exclude_unset=True)
    data["owner_id"] = user_id
    data["is_active"] = True

    response = supabase.table("shops").insert(data).execute()
    shop = (response.data or [None])[0]
    if not shop:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unable to create shop",
        )
    return shop


def get_my_shop(user_id: str, shop_id: str) -> dict:
    response = (
        supabase.table("shops")
        .select("*")
        .eq("id", shop_id)
        .eq("owner_id", user_id)
        .eq("is_active", True)
        .maybe_single()
        .execute()
    )
    if not response.data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Shop not found",
        )
    return response.data


def update_shop(user_id: str, shop_id: str, payload: ShopUpdate) -> dict:
    get_my_shop(user_id, shop_id)
    data = payload.model_dump(exclude_unset=True)
    if not data:
        return get_my_shop(user_id, shop_id)

    response = (
        supabase.table("shops")
        .update(data)
        .eq("id", shop_id)
        .eq("owner_id", user_id)
        .execute()
    )
    shop = (response.data or [None])[0]
    if not shop:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Shop not found",
        )
    return shop


def list_shop_products(user_id: str, shop_id: str) -> list[dict]:
    get_my_shop(user_id, shop_id)
    response = (
        supabase.table("products")
        .select("*")
        .eq("shop_id", shop_id)
        .order("created_at", desc=True)
        .execute()
    )
    return response.data or []


def create_shop_product(user_id: str, shop_id: str, payload: ProductCreate) -> dict:
    get_my_shop(user_id, shop_id)
    data = payload.model_dump(exclude_unset=True)
    data["shop_id"] = shop_id

    response = supabase.table("products").insert(data).execute()
    product = (response.data or [None])[0]
    if not product:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unable to create product",
        )
    return product


def update_shop_product(
    user_id: str,
    shop_id: str,
    product_id: str,
    payload: ProductUpdate,
) -> dict:
    get_my_shop(user_id, shop_id)
    data = payload.model_dump(exclude_unset=True)
    if not data:
        response = (
            supabase.table("products")
            .select("*")
            .eq("id", product_id)
            .eq("shop_id", shop_id)
            .maybe_single()
            .execute()
        )
        if not response.data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Product not found",
            )
        return response.data

    response = (
        supabase.table("products")
        .update(data)
        .eq("id", product_id)
        .eq("shop_id", shop_id)
        .execute()
    )
    product = (response.data or [None])[0]
    if not product:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Product not found",
        )
    return product


def list_shop_orders(user_id: str, shop_id: str) -> list[dict]:
    get_my_shop(user_id, shop_id)
    response = (
        supabase.table("orders")
        .select("*,order_items(*)")
        .eq("shop_id", shop_id)
        .order("created_at", desc=True)
        .execute()
    )
    orders = response.data or []
    for order in orders:
        order["order_items"] = order.get("order_items") or []
    return orders


def update_shop_order_status(user_id: str, shop_id: str, order_id: str, status_value: str) -> dict:
    get_my_shop(user_id, shop_id)
    allowed_statuses = {"pending", "confirmed", "shipping", "completed", "cancelled"}
    if status_value not in allowed_statuses:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid order status",
        )

    response = (
        supabase.table("orders")
        .update({"status": status_value})
        .eq("id", order_id)
        .eq("shop_id", shop_id)
        .execute()
    )
    order = (response.data or [None])[0]
    if not order:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Order not found",
        )
    return order
