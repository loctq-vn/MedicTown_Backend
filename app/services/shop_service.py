import logging
from app.services import notification_service

logger = logging.getLogger(__name__)

from datetime import datetime, timezone
from decimal import Decimal
from uuid import uuid4

from fastapi import HTTPException, status

from app.config import settings
from app.database import get_service_supabase_client, supabase
from app.schemas.product_schema import ProductCreate, ProductUpdate
from app.schemas.shop_schema import ShopCreate, ShopUpdate
from app.services.order_service import (
    cancel_order_and_restore_stock,
    confirm_order_and_deduct_stock,
    normalize_order_relations,
)
from app.services.upload_validation import validate_image_upload


SHOP_ORDER_STATUS_TRANSITIONS = {
    "confirmed": {"pending"},
    "shipping": {"confirmed"},
    "completed": {"shipping"},
    "cancelled": {"pending", "confirmed", "shipping", "cancelled"},
}


def _apply_subcategory_rules(data: dict, current_product: dict | None = None) -> None:
    subcategory_id = data.get("subcategory_id") or (
        current_product or {}
    ).get("subcategory_id")
    if not subcategory_id:
        return

    response = (
        supabase.table("product_subcategories")
        .select("id,requires_prescription_default,is_active")
        .eq("id", subcategory_id)
        .eq("is_active", True)
        .maybe_single()
        .execute()
    )
    subcategory = response.data
    if not subcategory:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid product subcategory",
        )
    if subcategory.get("requires_prescription_default"):
        data["requires_prescription"] = True


def _validate_product_business_rules(data: dict, current_product: dict | None = None) -> None:
    current_product = current_product or {}
    price = data.get("price", current_product.get("price"))
    sale_price = data.get("sale_price", current_product.get("sale_price"))
    images = data.get("images", current_product.get("images") or [])

    if not images:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Product must have at least one image",
        )

    if sale_price is None:
        return

    if float(sale_price) < 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Sale price must be greater than or equal to 0",
        )
    if price is not None and float(sale_price) > float(price):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Sale price must be less than or equal to price",
        )


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


def get_main_shop() -> dict:
    response = (
        supabase.table("shops")
        .select("*")
        .eq("id", str(settings.main_shop_id))
        .eq("is_active", True)
        .maybe_single()
        .execute()
    )
    if not response.data:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Main shop is not available",
        )
    return response.data


def get_main_shop_id() -> str:
    return str(get_main_shop()["id"])


def require_main_shop_owner(user_id: str) -> dict:
    shop = get_main_shop()
    if str(shop["owner_id"]) != str(user_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Main shop owner access required",
        )
    return shop


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
    _apply_subcategory_rules(data)
    _validate_product_business_rules(data)

    response = supabase.table("products").insert(data).execute()
    product = (response.data or [None])[0]
    if not product:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unable to create product",
        )
    return product


async def upload_product_image(
    user_id: str,
    shop_id: str,
    content: bytes,
    content_type: str | None = None,
    filename: str | None = None,
) -> dict:
    get_my_shop(user_id, shop_id)
    extension, content_type = validate_image_upload(content, content_type, filename)
    file_path = f"shops/{shop_id}/products/upload_{uuid4().hex}.{extension}"

    try:
        supabase.storage.from_(settings.supabase_storage_bucket).upload(
            file_path,
            content,
            file_options={"content-type": content_type, "upsert": "true"},
        )
        public_url = supabase.storage.from_(settings.supabase_storage_bucket).get_public_url(
            file_path
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unable to upload product image",
        ) from exc

    return {
        "path": file_path,
        "url": public_url,
    }


def update_shop_product(
    user_id: str,
    shop_id: str,
    product_id: str,
    payload: ProductUpdate,
) -> dict:
    get_my_shop(user_id, shop_id)
    current_response = (
        supabase.table("products")
        .select("*")
        .eq("id", product_id)
        .eq("shop_id", shop_id)
        .maybe_single()
        .execute()
    )
    if not current_response.data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Product not found",
        )

    data = payload.model_dump(exclude_unset=True)
    if not data:
        return current_response.data

    if data.get("price") == 0 and "sale_price" not in data:
        data["sale_price"] = None

    _apply_subcategory_rules(data, current_response.data)
    _validate_product_business_rules(data, current_response.data)

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
        .select("*,order_items(*),payments(*)")
        .eq("shop_id", shop_id)
        .order("created_at", desc=True)
        .execute()
    )
    orders = response.data or []
    for order in orders:
        normalize_order_relations(order)
    return orders


def update_shop_order_status(user_id: str, shop_id: str, order_id: str, status_value: str) -> dict:
    get_my_shop(user_id, shop_id)
    next_status = status_value.strip().lower()
    if next_status not in SHOP_ORDER_STATUS_TRANSITIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid order status",
        )

    current_response = (
        supabase.table("orders")
        .select("id,user_id,status,total_amount")
        .eq("id", order_id)
        .eq("shop_id", shop_id)
        .maybe_single()
        .execute()
    )
    current_order = current_response.data
    if not current_order:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Order not found",
        )

    current_status = (current_order.get("status") or "").strip().lower()
    if not _is_valid_shop_order_status_transition(current_status, next_status):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "Invalid order status transition: "
                f"{current_status or 'unknown'} -> {next_status}"
            ),
        )

    if current_status == "pending" and next_status == "confirmed":
        order = confirm_order_and_deduct_stock(supabase, shop_id, order_id)

    elif next_status == "cancelled":
        order = cancel_order_and_restore_stock(supabase, shop_id, order_id)

    else:
        response = (
            supabase.table("orders")
            .update({"status": next_status})
            .eq("id", order_id)
            .eq("shop_id", shop_id)
            .eq("status", current_status)
            .execute()
        )
        order = (response.data or [None])[0]

        if not order:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Order status was changed by another request",
            )

        if next_status == "completed":
            _ensure_completed_cash_payment_if_unpaid(order)

    order.setdefault("user_id", current_order["user_id"])

    try:
        notification_service.send_order_status_notification(order)
    except Exception:
        logger.exception("Order updated, but notification delivery failed")

    return order


def _is_valid_shop_order_status_transition(current_status: str, next_status: str) -> bool:
    return current_status in SHOP_ORDER_STATUS_TRANSITIONS.get(next_status, set())


def _ensure_completed_cash_payment_if_unpaid(order: dict) -> None:
    client = get_service_supabase_client()
    completed_payment_response = (
        client.table("payments")
        .select("id")
        .eq("order_id", order["id"])
        .eq("status", "completed")
        .limit(1)
        .execute()
    )
    if completed_payment_response.data:
        return

    now = datetime.now(timezone.utc).isoformat()
    amount = float(Decimal(str(order.get("total_amount") or 0)))
    cash_payment_response = (
        client.table("payments")
        .select("*")
        .eq("order_id", order["id"])
        .eq("method", "cash")
        .order("created_at", desc=True)
        .limit(1)
        .execute()
    )
    cash_payment = (cash_payment_response.data or [None])[0]
    payment_data = {
        **((cash_payment or {}).get("payment_data") or {}),
        "completed_by": "shop_order_completion",
    }
    completed_payload = {
        "amount": amount,
        "status": "completed",
        "payment_data": payment_data,
        "paid_at": (cash_payment or {}).get("paid_at") or now,
        "updated_at": now,
    }

    if cash_payment:
        response = (
            client.table("payments")
            .update(completed_payload)
            .eq("id", cash_payment["id"])
            .execute()
        )
    else:
        response = (
            client.table("payments")
            .insert(
                {
                    **completed_payload,
                    "order_id": order["id"],
                    "method": "cash",
                    "transaction_id": f"CASH_{uuid4().hex[:12]}",
                }
            )
            .execute()
        )

    if not (response.data or []):
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unable to create completed cash payment",
        )
