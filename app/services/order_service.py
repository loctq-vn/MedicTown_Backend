from decimal import Decimal
from itertools import groupby
from operator import itemgetter

from fastapi import HTTPException, status

from app.database import supabase
from app.schemas.order_schema import OrderCreate


def normalize_order_relations(order: dict) -> dict:
    order["order_items"] = _normalize_relation_list(order.get("order_items"))
    order["payments"] = _normalize_relation_list(order.get("payments"))
    return order


def _normalize_relation_list(value):
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]


def create_order(user_id: str, payload: OrderCreate) -> list[dict]:
    from app.services import payment_service

    requested_payment_method = (payload.payment_method or "").strip().lower()
    payment_method = payment_service.normalize_payment_method(payload.payment_method)
    if payment_method == "momo" and not payment_service.is_fake_payment_method(requested_payment_method):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Use MoMo checkout endpoint for MoMo payments",
        )
    if not payload.cart_item_ids and not payload.direct_items:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="cart_item_ids or direct_items is required",
        )

    order_items = _load_order_request_items(user_id, payload)
    if not order_items:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Order has no valid items",
        )

    grouped_items = _group_items_by_shop(order_items)
    shipping_info = _resolve_shipping_info(user_id, payload)
    created_orders = [
        _create_order_for_shop(
            client=supabase,
            user_id=user_id,
            payment_method=payment_method,
            payment_status="pending",
            shipping_info=shipping_info,
            note=payload.note,
            shop_id=shop_id,
            items=items,
        )
        for shop_id, items in grouped_items
    ]

    for order in created_orders:
        payment = create_immediate_order_payment(
            order,
            payment_method,
            "pending",
            Decimal(str(order["total_amount"])),
        )
        order["payments"] = [payment]
        normalize_order_relations(order)

    if payload.cart_item_ids:
        _delete_created_cart_items(user_id, payload.cart_item_ids)

    return created_orders


def confirm_order_and_deduct_stock(client, shop_id: str | None, order_id: str) -> dict:
    response = (
        client.rpc(
            "confirm_shop_order_and_deduct_stock",
            {
                "p_shop_id": shop_id,
                "p_order_id": order_id,
            },
        )
        .execute()
    )
    return _first_rpc_row(response.data)


def cancel_order_and_restore_stock(client, shop_id: str | None, order_id: str) -> dict:
    response = (
        client.rpc(
            "cancel_shop_order_and_restore_stock",
            {
                "p_shop_id": shop_id,
                "p_order_id": order_id,
            },
        )
        .execute()
    )
    return _first_rpc_row(response.data)


def _first_rpc_row(data) -> dict:
    if isinstance(data, list):
        return (data or [None])[0] or {}
    return data or {}


def list_orders(user_id: str) -> list[dict]:
    response = (
        supabase.table("orders")
        .select("*,order_items(*),payments(*)")
        .eq("user_id", user_id)
        .order("created_at", desc=True)
        .execute()
    )

    orders = response.data or []
    for order in orders:
        normalize_order_relations(order)
    return orders


def _load_order_request_items(user_id: str, payload: OrderCreate) -> list[dict]:
    items: list[dict] = []

    if payload.cart_item_ids:
        cart_response = (
            supabase.table("cart_items")
            .select(
                "id,product_id,quantity,"
                "products(id,name,price,sale_price,images,shop_id,stock,is_active)"
            )
            .eq("user_id", user_id)
            .in_("id", payload.cart_item_ids)
            .execute()
        )
        cart_items = cart_response.data or []
        if len(cart_items) != len(set(payload.cart_item_ids)):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="One or more cart items were not found",
            )

        for cart_item in cart_items:
            product = cart_item.get("products") or {}
            if not product.get("id"):
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="One or more products were not found",
                )
            order_item = _build_order_item_from_product(
                product,
                int(cart_item.get("quantity") or 0),
            )
            order_item["cart_item_id"] = cart_item.get("id")
            items.append(order_item)

    if payload.direct_items:
        direct_quantities: dict[str, int] = {}
        for item in payload.direct_items:
            direct_quantities[item.product_id] = (
                direct_quantities.get(item.product_id, 0) + item.quantity
            )

        products_response = (
            supabase.table("products")
            .select("id,name,price,sale_price,images,shop_id,stock,is_active")
            .in_("id", list(direct_quantities.keys()))
            .execute()
        )
        products = products_response.data or []
        product_by_id = {product["id"]: product for product in products}
        missing_ids = [
            product_id
            for product_id in direct_quantities
            if product_id not in product_by_id
        ]
        if missing_ids:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="One or more products were not found",
            )

        for product_id, quantity in direct_quantities.items():
            items.append(
                _build_order_item_from_product(product_by_id[product_id], quantity)
            )

    return items


def _build_order_item_from_product(product: dict, quantity: int) -> dict:
    if quantity <= 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Quantity must be greater than zero",
        )
    if product.get("is_active") is False:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Product is not active",
        )
    if not product.get("id"):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Product not found",
        )

    stock = int(product.get("stock") or 0)
    if quantity > stock:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Quantity exceeds product stock",
        )

    price = product.get("sale_price")
    if price is None or Decimal(str(price)) <= 0:
        price = product.get("price")

    return {
        "product_id": product["id"],
        "product_name": product.get("name") or "",
        "product_image": _first_product_image(product.get("images")),
        "price": Decimal(str(price or 0)),
        "quantity": quantity,
        "shop_id": product.get("shop_id"),
    }


def _first_product_image(images) -> str | None:
    if isinstance(images, list):
        return images[0] if images else None
    if isinstance(images, str):
        return images or None
    return None


def _group_items_by_shop(items: list[dict]) -> list[tuple[str | None, list[dict]]]:
    sorted_items = sorted(items, key=lambda item: item.get("shop_id") or "")
    return [
        (shop_id, list(shop_items))
        for shop_id, shop_items in groupby(sorted_items, key=itemgetter("shop_id"))
    ]


def _resolve_shipping_info(user_id: str, payload: OrderCreate) -> dict:
    shipping_address = (payload.shipping_address or "").strip()
    if not shipping_address:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="shipping_address is required",
        )

    shipping_name = (payload.shipping_name or "").strip()
    shipping_phone = (payload.shipping_phone or "").strip()
    if not shipping_name or not shipping_phone:
        address_response = (
            supabase.table("address")
            .select("recipient_name,phone_number,location")
            .eq("user_id", user_id)
            .eq("location", shipping_address)
            .limit(1)
            .execute()
        )
        address = (address_response.data or [None])[0]
        if address:
            shipping_name = (
                shipping_name
                or (address.get("recipient_name") or "").strip()
            )
            shipping_phone = (
                shipping_phone
                or (address.get("phone_number") or "").strip()
            )

    if not shipping_name or not shipping_phone:
        user_response = (
            supabase.table("users")
            .select("name,phone")
            .eq("id", user_id)
            .limit(1)
            .execute()
        )
        user = (user_response.data or [None])[0]
        if user:
            shipping_name = shipping_name or (user.get("name") or "").strip()
            shipping_phone = shipping_phone or (user.get("phone") or "").strip()

    if not shipping_name or not shipping_phone:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="shipping_name and shipping_phone are required",
        )

    return {
        "shipping_name": shipping_name,
        "shipping_phone": shipping_phone,
        "shipping_address": shipping_address,
    }


def _create_order_for_shop(
    client,
    user_id: str,
    payment_method: str,
    payment_status: str,
    shipping_info: dict,
    note: str | None,
    shop_id: str | None,
    items: list[dict],
) -> dict:
    total_amount = sum(
        item["price"] * item["quantity"]
        for item in items
    )
    order_response = (
        client.table("orders")
        .insert(
            {
                "user_id": user_id,
                "status": "pending",
                "total_amount": float(total_amount),
                "note": note,
                "shipping_name": shipping_info["shipping_name"],
                "shipping_phone": shipping_info["shipping_phone"],
                "shipping_address": shipping_info["shipping_address"],
                "shop_id": shop_id,
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

    order_item_payloads = [
        {
            "order_id": order["id"],
            "product_id": item["product_id"],
            "product_name": item["product_name"],
            "product_image": item["product_image"],
            "price": float(item["price"]),
            "quantity": item["quantity"],
        }
        for item in items
    ]
    order_items_response = (
        client.table("order_items")
        .insert(order_item_payloads)
        .execute()
    )
    order_items = order_items_response.data or []
    if not order_items:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unable to create order items",
        )

    order["order_items"] = order_items
    order["payments"] = []
    if payment_status == "completed":
        order = confirm_order_and_deduct_stock(client, shop_id, order["id"])
        order["order_items"] = order_items
        order["payments"] = []
    return order


def _delete_created_cart_items(user_id: str, cart_item_ids: list[str]) -> None:
    (
        supabase.table("cart_items")
        .delete()
        .eq("user_id", user_id)
        .in_("id", cart_item_ids)
        .execute()
    )


def create_immediate_order_payment(
    order: dict,
    payment_method: str,
    payment_status: str,
    amount: Decimal,
) -> dict:
    payment_response = (
        supabase.table("payments")
        .insert(
            {
                "order_id": order["id"],
                "method": payment_method,
                "amount": float(amount),
                "status": payment_status,
                "payment_data": {},
            }
        )
        .execute()
    )
    payment = (payment_response.data or [None])[0]
    if not payment:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unable to create payment",
        )
    return payment


def create_order_from_payment_snapshot(client, payment: dict) -> dict:
    payment_data = payment.get("payment_data") or {}
    user_id = payment_data.get("user_id")
    cart_snapshot = payment_data.get("cart_snapshot") or []
    shipping_info = payment_data.get("shipping_info") or {}
    note = payment_data.get("note")

    if not user_id or not cart_snapshot:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Payment snapshot is incomplete",
        )

    items = [
        {
            "product_id": item["product_id"],
            "product_name": item.get("product_name") or "",
            "product_image": item.get("product_image"),
            "price": Decimal(str(item.get("price") or 0)),
            "quantity": int(item.get("quantity") or 0),
            "shop_id": item.get("shop_id"),
        }
        for item in cart_snapshot
    ]
    grouped_items = _group_items_by_shop(items)
    if len(grouped_items) != 1:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="MoMo checkout supports one shop per payment",
        )

    shop_id, shop_items = grouped_items[0]
    order = _create_order_for_shop(
        client=client,
        user_id=user_id,
        payment_method="momo",
        payment_status="completed",
        shipping_info=shipping_info,
        note=note,
        shop_id=shop_id,
        items=shop_items,
    )
    normalize_order_relations(order)
    return order


def delete_cart_items_for_paid_snapshot(client, payment: dict) -> None:
    payment_data = payment.get("payment_data") or {}
    user_id = payment_data.get("user_id")
    cart_item_ids = [
        item.get("cart_item_id")
        for item in payment_data.get("cart_snapshot") or []
        if item.get("cart_item_id")
    ]
    if not user_id or not cart_item_ids:
        return

    (
        client.table("cart_items")
        .delete()
        .eq("user_id", user_id)
        .in_("id", cart_item_ids)
        .execute()
    )
