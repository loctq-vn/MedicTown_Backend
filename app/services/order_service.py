from decimal import Decimal
from uuid import uuid4

from fastapi import HTTPException, status

from app.database import supabase
from app.schemas.order_schema import OrderCreate
from app.services import payment_service


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
    payment_method = payment_service.normalize_payment_method(payload.payment_method)
    if not payload.cart_item_ids and not payload.direct_items:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="cart_item_ids or direct_items is required",
        )

    payment_id = str(uuid4()) if payment_method == "momo" else None
    response = (
        supabase.rpc(
            "create_order_transaction",
            {
                "p_user_id": user_id,
                "p_cart_item_ids": payload.cart_item_ids,
                "p_direct_items": [
                    item.model_dump()
                    for item in payload.direct_items
                ],
                "p_payment_method": payment_method,
                "p_shipping_address": payload.shipping_address,
                "p_note": payload.note,
                "p_payment_id": payment_id,
                "p_payment_status": "processing" if payment_method == "momo" else "pending",
                "p_payment_data": {},
            },
        )
        .execute()
    )

    created_orders = response.data or []
    if not isinstance(created_orders, list):
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unexpected create_order_transaction response",
        )

    for order in created_orders:
        normalize_order_relations(order)
        if payment_method == "momo":
            if len(created_orders) > 1:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="MoMo checkout currently supports one shop per order",
                )
            payment = payment_service.attach_momo_checkout_data(
                order,
                order["payments"][0],
                Decimal(str(order["total_amount"])),
            )
            order["payments"] = [payment]

    return created_orders


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
