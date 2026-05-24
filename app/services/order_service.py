from collections import defaultdict
from decimal import Decimal

from fastapi import HTTPException, status

from app.database import supabase
from app.schemas.order_schema import OrderCreate


def _load_cart_items(user_id: str, cart_item_ids: list[str]) -> list[dict]:
    unique_ids = list(dict.fromkeys(cart_item_ids))
    if not unique_ids:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="cart_item_ids is required",
        )

    response = (
        supabase.table("cart_items")
        .select("id,user_id,product_id,quantity,products(id,name,price,sale_price,stock,images,is_active,shop_id)")
        .eq("user_id", user_id)
        .in_("id", unique_ids)
        .execute()
    )
    cart_items = response.data or []
    found_ids = {item["id"] for item in cart_items}
    missing_ids = set(unique_ids) - found_ids
    if missing_ids:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Some cart items do not belong to current user",
        )
    return cart_items


def _load_direct_items(direct_items: list[dict]) -> list[dict]:
    unique_ids = list(dict.fromkeys(item["product_id"] for item in direct_items))
    quantities = {item["product_id"]: int(item["quantity"]) for item in direct_items}
    if not unique_ids:
        return []

    response = (
        supabase.table("products")
        .select("id,name,price,sale_price,stock,images,is_active,shop_id")
        .in_("id", unique_ids)
        .execute()
    )
    products = response.data or []
    found_ids = {item["id"] for item in products}
    missing_ids = set(unique_ids) - found_ids
    if missing_ids:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Some products were not found",
        )

    return [
        {
            "id": f"direct:{product['id']}",
            "product_id": product["id"],
            "quantity": quantities[product["id"]],
            "products": product,
        }
        for product in products
    ]


def _normalize_order_item(cart_item: dict) -> tuple[dict, Decimal, str | None]:
    product = cart_item.get("products")
    if not product:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Product not found for cart item",
        )
    if product.get("is_active") is False:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Product is not active: {product.get('name') or product.get('id')}",
        )

    quantity = int(cart_item.get("quantity") or 0)
    stock = int(product.get("stock") or 0)
    if quantity <= 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid cart item quantity",
        )
    if quantity > stock:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Quantity exceeds product stock: {product.get('name') or product.get('id')}",
        )

    unit_price = Decimal(str(product.get("sale_price") or product.get("price") or 0))
    images = product.get("images") or []
    order_item = {
        "product_id": product["id"],
        "product_name": product.get("name"),
        "product_image": images[0] if images else None,
        "price": float(unit_price),
        "quantity": quantity,
    }
    return order_item, unit_price * Decimal(str(quantity)), product.get("shop_id")


def _resolve_shipping_address(user_id: str, shipping_address: str | None) -> dict:
    if not shipping_address:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="shipping_address is required",
        )

    response = (
        supabase.table("address")
        .select("recipient_name,phone_number,location")
        .eq("user_id", user_id)
        .eq("location", shipping_address)
        .limit(1)
        .execute()
    )
    address = (response.data or [None])[0]
    if not address:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Shipping address does not belong to current user",
        )
    if not address.get("recipient_name") or not address.get("phone_number"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Shipping address is missing recipient name or phone number",
        )
    return address


def create_order(user_id: str, payload: OrderCreate) -> list[dict]:
    if not payload.payment_method:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="payment_method is required",
        )

    cart_items = _load_cart_items(user_id, payload.cart_item_ids) if payload.cart_item_ids else []
    direct_items = _load_direct_items([item.model_dump() for item in payload.direct_items])
    order_source_items = cart_items + direct_items
    if not order_source_items:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="cart_item_ids or direct_items is required",
        )

    shipping_address = _resolve_shipping_address(user_id, payload.shipping_address)

    groups: dict[str | None, dict] = defaultdict(
        lambda: {"items": [], "total_amount": Decimal("0")}
    )
    for cart_item in order_source_items:
        order_item, line_total, shop_id = _normalize_order_item(cart_item)
        groups[shop_id]["items"].append(order_item)
        groups[shop_id]["total_amount"] += line_total

    created_orders = []
    for shop_id, group in groups.items():
        order_response = (
            supabase.table("orders")
            .insert(
                {
                    "user_id": user_id,
                    "status": "pending",
                    "payment_method": payload.payment_method,
                    "total_amount": float(group["total_amount"]),
                    "shipping_name": shipping_address["recipient_name"],
                    "shipping_phone": shipping_address["phone_number"],
                    "shipping_address": shipping_address["location"],
                    "shop_id": shop_id,
                    "note": payload.note,
                }
            )
            .execute()
        )

        order = (order_response.data or [None])[0]
        if not order:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Unable to create order",
            )

        order_items = [
            {
                **item,
                "order_id": order["id"],
            }
            for item in group["items"]
        ]
        items_response = supabase.table("order_items").insert(order_items).execute()
        order["order_items"] = items_response.data or []
        created_orders.append(order)

    if cart_items:
        supabase.table("cart_items").delete().eq("user_id", user_id).in_(
            "id",
            [item["id"] for item in cart_items],
        ).execute()

    return created_orders


def list_orders(user_id: str) -> list[dict]:
    response = (
        supabase.table("orders")
        .select("*,order_items(*)")
        .eq("user_id", user_id)
        .order("created_at", desc=True)
        .execute()
    )

    orders = response.data or []
    for order in orders:
        order["order_items"] = order.get("order_items") or []
    return orders
