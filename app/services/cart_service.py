from fastapi import HTTPException, status
from postgrest.exceptions import APIError

from app.database import supabase
from app.schemas.cart_schema import CartItemCreate, CartItemUpdate
from app.utils.postgrest_filters import parse_eq_filter, parse_in_filter


def _get_active_product(product_id: str) -> dict:
    response = (
        supabase.table("products")
        .select("id,stock,is_active")
        .eq("id", product_id)
        .maybe_single()
        .execute()
    )
    product = response.data
    if not product:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Product not found",
        )
    if product.get("is_active") is False:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Product is not active",
        )
    return product


def _ensure_stock(product: dict, quantity: int) -> None:
    stock = int(product.get("stock") or 0)
    if quantity > stock:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Quantity exceeds product stock",
        )


def list_cart_items(user_id: str, product_id: str | None = None) -> list[dict]:
    product_id = parse_eq_filter(product_id)
    query = supabase.table("cart_items").select("*,products(*)").eq("user_id", user_id)
    if product_id:
        query = query.eq("product_id", product_id)

    try:
        response = query.order("added_at", desc=True).execute()
    except APIError as exc:
        if exc.args and isinstance(exc.args[0], dict) and exc.args[0].get("code") == "42703":
            response = query.execute()
        else:
            raise

    return response.data or []


def add_to_cart(user_id: str, payload: CartItemCreate) -> dict:
    product = _get_active_product(payload.product_id)
    existing = list_cart_items(user_id, payload.product_id)
    if existing:
        cart_item = existing[0]
        quantity = int(cart_item.get("quantity", 0)) + payload.quantity
        _ensure_stock(product, quantity)
        return update_cart_item(
            user_id,
            cart_item["id"],
            CartItemUpdate(quantity=quantity),
        )

    _ensure_stock(product, payload.quantity)
    response = (
        supabase.table("cart_items")
        .insert(
            {
                "user_id": user_id,
                "product_id": payload.product_id,
                "quantity": payload.quantity,
            }
        )
        .execute()
    )
    cart_item = (response.data or [None])[0]
    if not cart_item:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unable to add cart item",
        )
    return cart_item


def update_cart_item(user_id: str, cart_item_id: str, payload: CartItemUpdate) -> dict:
    current_response = (
        supabase.table("cart_items")
        .select("id,product_id")
        .eq("id", cart_item_id)
        .eq("user_id", user_id)
        .maybe_single()
        .execute()
    )
    current_item = current_response.data
    if not current_item:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Cart item not found",
        )

    product = _get_active_product(current_item["product_id"])
    _ensure_stock(product, payload.quantity)

    response = (
        supabase.table("cart_items")
        .update(payload.model_dump())
        .eq("id", cart_item_id)
        .eq("user_id", user_id)
        .execute()
    )
    cart_item = (response.data or [None])[0]
    if not cart_item:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Cart item not found",
        )
    return cart_item


def delete_cart_item(user_id: str, cart_item_id: str) -> None:
    cart_item_id = parse_eq_filter(cart_item_id) or cart_item_id
    response = (
        supabase.table("cart_items")
        .delete()
        .eq("id", cart_item_id)
        .eq("user_id", user_id)
        .execute()
    )
    if not response.data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Cart item not found",
        )


def clear_cart(user_id: str) -> None:
    supabase.table("cart_items").delete().eq("user_id", user_id).execute()


def delete_cart_items(user_id: str, cart_item_ids: list[str]) -> None:
    if not cart_item_ids:
        return

    response = (
        supabase.table("cart_items")
        .delete()
        .in_("id", cart_item_ids)
        .eq("user_id", user_id)
        .execute()
    )
    if not response.data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Cart items not found",
        )


def delete_cart_items_from_filter(user_id: str, id_filter: str | None) -> None:
    ids = parse_in_filter(id_filter)
    if ids:
        delete_cart_items(user_id, ids)
        return

    cart_item_id = parse_eq_filter(id_filter)
    if cart_item_id:
        delete_cart_item(user_id, cart_item_id)
        return

    clear_cart(user_id)
