import hashlib
import hmac
import json
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from urllib.parse import urlsplit, urlunsplit
from uuid import uuid4

import httpx
from fastapi import HTTPException, status

from app.config import settings
from app.database import get_service_supabase_client, supabase
from app.schemas.order_schema import FakePaymentMethodCreate, OrderCreate
from app.services import order_service


MOMO_SUCCESS_CODE = 0
MOMO_PAYMENT_TTL_MINUTES = 15
MOMO_MIN_AMOUNT = 1000
MOMO_MAX_AMOUNT = 50_000_000


def normalize_payment_method(payment_method: str | None) -> str:
    normalized = (payment_method or "").strip().lower()
    aliases = {
        "cod": "cash",
        "cash": "cash",
        "momo": "momo",
        "fake_momo": "momo",
        "wallet": "wallet",
        "vnpay": "vnpay",
        "fake_vnpay": "vnpay",
    }
    method = aliases.get(normalized)
    if not method:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Unsupported payment method",
        )
    return method


def is_fake_payment_method(payment_method: str | None) -> bool:
    return (payment_method or "").strip().lower() in {"fake_momo", "fake_vnpay"}


def create_initial_payment(
    order: dict,
    method: str,
    amount: Decimal,
    payment_status: str | None = None,
    payment_data: dict | None = None,
    payment_id: str | None = None,
) -> dict:
    if payment_status is None:
        payment_status = "processing" if method == "momo" else "pending"
    insert_payload = {
        "order_id": order["id"],
        "method": method,
        "amount": float(amount),
        "status": payment_status,
        "payment_data": payment_data or {},
    }
    if payment_id:
        insert_payload["id"] = payment_id

    response = (
        supabase.table("payments")
        .insert(insert_payload)
        .execute()
    )
    payment = (response.data or [None])[0]
    if not payment:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unable to create payment",
        )
    return payment


def create_momo_payment(order: dict, amount: Decimal) -> dict:
    payment_id = str(uuid4())
    payment_data, payment_status = create_momo_checkout_data(order, payment_id, amount)
    return create_initial_payment(
        order,
        "momo",
        amount,
        payment_status=payment_status,
        payment_data=payment_data,
        payment_id=payment_id,
    )


def attach_momo_checkout_data(order: dict, payment: dict, amount: Decimal) -> dict:
    payment_id = payment["id"]
    payment_data, payment_status = create_momo_checkout_data(order, payment_id, amount)
    response = (
        supabase.table("payments")
        .update(
            {
                "status": payment_status,
                "payment_data": payment_data,
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }
        )
        .eq("id", payment_id)
        .execute()
    )
    updated_payment = (response.data or [None])[0]
    if not updated_payment:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unable to update MoMo payment",
        )
    return updated_payment


def create_fake_payment_method(user_id: str, payload: FakePaymentMethodCreate) -> dict:
    if (settings.environment or "").strip().lower() == "production":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Fake payments are disabled in production",
        )

    requested_method = (payload.method or "").strip().lower()
    method = normalize_payment_method(requested_method)
    if requested_method not in {"fake_momo", "fake_vnpay"} or method not in {"momo", "vnpay"}:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Unsupported fake payment method",
        )

    client = get_service_supabase_client()
    order = _load_user_order_for_fake_payment(client, user_id, payload.order_id)
    if (order.get("status") or "").strip().lower() == "pending":
        order_service.confirm_order_and_deduct_stock(client, order.get("shop_id"), order["id"])

    return _upsert_completed_fake_payment(client, order, method, requested_method)


def _load_user_order_for_fake_payment(client, user_id: str, order_id: str) -> dict:
    response = (
        client.table("orders")
        .select("id,user_id,shop_id,total_amount,status")
        .eq("id", order_id)
        .eq("user_id", user_id)
        .limit(1)
        .execute()
    )
    order = (response.data or [None])[0]
    if not order:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Order not found",
        )
    return order


def _upsert_completed_fake_payment(
    client,
    order: dict,
    method: str,
    requested_method: str,
) -> dict:
    now = datetime.now(timezone.utc).isoformat()
    existing_payment = _load_latest_order_payment(client, order["id"], method)
    payment_data = {
        **((existing_payment or {}).get("payment_data") or {}),
        "fake_payment": True,
        "fake_method": requested_method,
        "completed_by": "api/payments/fake/method",
    }
    completed_payload = {
        "method": method,
        "amount": float(Decimal(str(order.get("total_amount") or 0))),
        "status": "completed",
        "transaction_id": f"FAKE_{method.upper()}_{uuid4().hex[:12]}",
        "payment_data": payment_data,
        "paid_at": now,
        "updated_at": now,
    }

    if existing_payment:
        response = (
            client.table("payments")
            .update(completed_payload)
            .eq("id", existing_payment["id"])
            .execute()
        )
    else:
        response = (
            client.table("payments")
            .insert(
                {
                    **completed_payload,
                    "order_id": order["id"],
                }
            )
            .execute()
        )

    payment = (response.data or [None])[0]
    if not payment:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unable to create fake payment",
        )
    return payment


def _load_latest_order_payment(client, order_id: str, method: str) -> dict | None:
    response = (
        client.table("payments")
        .select("*")
        .eq("order_id", order_id)
        .eq("method", method)
        .in_("status", ["pending", "processing", "completed"])
        .order("created_at", desc=True)
        .limit(1)
        .execute()
    )
    return (response.data or [None])[0]


def create_momo_checkout(user_id: str, payload: OrderCreate) -> dict:
    _require_momo_settings()

    order_items = order_service._load_order_request_items(user_id, payload)
    if not order_items:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Payment has no valid items",
        )

    grouped_items = order_service._group_items_by_shop(order_items)
    if len(grouped_items) != 1:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="MoMo checkout supports one shop per payment",
        )

    shipping_info = order_service._resolve_shipping_info(user_id, payload)
    request_id = str(uuid4())
    expired_at = datetime.now(timezone.utc) + timedelta(minutes=MOMO_PAYMENT_TTL_MINUTES)
    cart_snapshot = [
        _serialize_cart_snapshot_item(item)
        for item in order_items
    ]
    total_amount = _calculate_snapshot_total(cart_snapshot)
    _validate_momo_amount(total_amount)
    payment_data = {
        "user_id": user_id,
        "cart_snapshot": cart_snapshot,
        "shipping_info": shipping_info,
        "note": payload.note,
        "total_amount": float(total_amount),
        "expired_at": expired_at.isoformat(),
        "request_id": request_id,
        "momo_request_id": request_id,
    }

    client = get_service_supabase_client()
    try:
        response = (
            client.table("payments")
            .insert(
                {
                    "id": request_id,
                    "order_id": None,
                    "method": "momo",
                    "amount": float(total_amount),
                    "status": "pending",
                    "payment_data": payment_data,
                }
            )
            .execute()
        )
    except httpx.HTTPError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Unable to connect to Supabase while creating MoMo payment",
        ) from exc
    payment = (response.data or [None])[0]
    if not payment:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unable to create MoMo payment",
        )

    try:
        gateway_data, gateway_status = create_momo_checkout_data_for_payment(
            request_id,
            total_amount,
        )
    except Exception as exc:
        failed_payment_data = {
            **payment_data,
            "momo_create_error": getattr(exc, "detail", str(exc)),
        }
        (
            client.table("payments")
            .update(
                {
                    "status": "failed",
                    "payment_data": failed_payment_data,
                    "updated_at": datetime.now(timezone.utc).isoformat(),
                }
            )
            .eq("id", request_id)
            .execute()
        )
        raise
    merged_payment_data = {
        **payment_data,
        **gateway_data,
    }
    update_payload = {
        "status": gateway_status,
        "payment_data": merged_payment_data,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    updated_response = (
        client.table("payments")
        .update(update_payload)
        .eq("id", request_id)
        .execute()
    )
    updated_payment = (updated_response.data or [None])[0]
    if not updated_payment:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unable to update MoMo payment",
        )
    return updated_payment


def _serialize_cart_snapshot_item(item: dict) -> dict:
    snapshot = {
        "product_id": item["product_id"],
        "product_name": item.get("product_name") or "",
        "product_image": item.get("product_image"),
        "price": float(item.get("price") or 0),
        "quantity": int(item.get("quantity") or 0),
        "shop_id": item.get("shop_id"),
    }
    if item.get("cart_item_id"):
        snapshot["cart_item_id"] = item["cart_item_id"]
    return snapshot


def _calculate_snapshot_total(cart_snapshot: list[dict]) -> Decimal:
    return sum(
        Decimal(str(item.get("price") or 0)) * int(item.get("quantity") or 0)
        for item in cart_snapshot
    )


def _validate_momo_amount(amount_value: Decimal) -> None:
    amount = int(amount_value)
    if amount < MOMO_MIN_AMOUNT or amount > MOMO_MAX_AMOUNT:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "MoMo payment amount must be between "
                f"{MOMO_MIN_AMOUNT} and {MOMO_MAX_AMOUNT} VND"
            ),
        )


def create_momo_checkout_data_for_payment(payment_id: str, amount_value: Decimal) -> tuple[dict, str]:
    _require_momo_settings()

    amount = int(amount_value)
    _validate_momo_amount(amount_value)

    request_id = payment_id
    order_id = f"MEDICTOWN-PAY-{payment_id}"
    order_info = f"Thanh toan MedicTown {payment_id[:8]}"
    extra_data = ""
    request_type = "captureWallet"
    ipn_url = settings.momo_ipn_url
    if not ipn_url:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="MOMO_IPN_URL is required for MoMo payments",
        )
    redirect_url = _resolve_momo_redirect_url(ipn_url)

    raw_signature = (
        f"accessKey={settings.momo_access_key}"
        f"&amount={amount}"
        f"&extraData={extra_data}"
        f"&ipnUrl={ipn_url}"
        f"&orderId={order_id}"
        f"&orderInfo={order_info}"
        f"&partnerCode={settings.momo_partner_code}"
        f"&redirectUrl={redirect_url}"
        f"&requestId={request_id}"
        f"&requestType={request_type}"
    )

    payload = {
        "partnerCode": settings.momo_partner_code,
        "requestId": request_id,
        "amount": amount,
        "orderId": order_id,
        "orderInfo": order_info,
        "redirectUrl": redirect_url,
        "ipnUrl": ipn_url,
        "requestType": request_type,
        "extraData": extra_data,
        "lang": "vi",
        "signature": _sign(raw_signature),
    }
    momo_response = _post_json(settings.momo_create_endpoint, payload)

    payment_data = {
        "momo_order_id": order_id,
        "momo_request_id": request_id,
        "momo_create_response": momo_response,
        "payUrl": momo_response.get("payUrl"),
        "deeplink": momo_response.get("deeplink"),
        "qrCodeUrl": momo_response.get("qrCodeUrl"),
    }
    payment_status = "pending"
    if momo_response.get("resultCode") != MOMO_SUCCESS_CODE:
        payment_status = "failed"
    return payment_data, payment_status


def create_momo_checkout_data(order: dict, payment_id: str, amount_value: Decimal) -> tuple[dict, str]:
    _require_momo_settings()

    amount = int(amount_value)
    _validate_momo_amount(amount_value)

    request_id = payment_id
    order_id = f"MEDICTOWN-{order['id']}"
    order_info = f"Thanh toan don hang MedicTown {order['id'][:8]}"
    extra_data = ""
    request_type = "captureWallet"
    ipn_url = settings.momo_ipn_url
    if not ipn_url:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="MOMO_IPN_URL is required for MoMo payments",
        )
    redirect_url = _resolve_momo_redirect_url(ipn_url)

    raw_signature = (
        f"accessKey={settings.momo_access_key}"
        f"&amount={amount}"
        f"&extraData={extra_data}"
        f"&ipnUrl={ipn_url}"
        f"&orderId={order_id}"
        f"&orderInfo={order_info}"
        f"&partnerCode={settings.momo_partner_code}"
        f"&redirectUrl={redirect_url}"
        f"&requestId={request_id}"
        f"&requestType={request_type}"
    )

    payload = {
        "partnerCode": settings.momo_partner_code,
        "requestId": request_id,
        "amount": amount,
        "orderId": order_id,
        "orderInfo": order_info,
        "redirectUrl": redirect_url,
        "ipnUrl": ipn_url,
        "requestType": request_type,
        "extraData": extra_data,
        "lang": "vi",
        "signature": _sign(raw_signature),
    }
    momo_response = _post_json(settings.momo_create_endpoint, payload)

    payment_data = {
        "momo_order_id": order_id,
        "momo_request_id": request_id,
        "momo_create_response": momo_response,
        "payUrl": momo_response.get("payUrl"),
        "deeplink": momo_response.get("deeplink"),
        "qrCodeUrl": momo_response.get("qrCodeUrl"),
    }
    payment_status = "processing"
    if momo_response.get("resultCode") != MOMO_SUCCESS_CODE:
        payment_status = "failed"
    return payment_data, payment_status


def handle_momo_ipn(payload: dict) -> dict:
    _require_momo_settings()
    if not _verify_momo_result_signature(payload):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid MoMo signature",
        )

    request_id = payload.get("requestId")
    if not request_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="requestId is required",
        )

    client = get_service_supabase_client()
    payment = _load_payment_for_ipn(client, request_id)
    _validate_momo_ipn_payload(payload, payment)

    if payment.get("status") != "pending":
        return {"resultCode": 0, "message": "Received"}

    current_payment_data = payment.get("payment_data") or {}
    merged_payment_data = {
        **current_payment_data,
        "momo_ipn_payload": payload,
    }

    if _payment_is_expired(payment):
        _update_payment_after_ipn(
            client,
            request_id,
            {
                "status": "expired",
                "payment_data": merged_payment_data,
                "updated_at": datetime.now(timezone.utc).isoformat(),
            },
        )
        return {"resultCode": 0, "message": "Received"}

    _validate_snapshot_amount(payment)

    result_code = _parse_int(payload.get("resultCode"), "resultCode")
    if result_code != MOMO_SUCCESS_CODE:
        _update_payment_after_ipn(
            client,
            request_id,
            {
                "status": "failed",
                "transaction_id": str(payload.get("transId")) if payload.get("transId") else None,
                "payment_data": merged_payment_data,
                "updated_at": datetime.now(timezone.utc).isoformat(),
            },
        )
        return {"resultCode": 0, "message": "Received"}

    order = order_service.create_order_from_payment_snapshot(client, payment)
    _update_payment_after_ipn(
        client,
        request_id,
        {
            "order_id": order["id"],
            "status": "completed",
            "transaction_id": str(payload.get("transId")) if payload.get("transId") else None,
            "payment_data": merged_payment_data,
            "paid_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat(),
        },
    )
    order_service.delete_cart_items_for_paid_snapshot(client, payment)
    return {"resultCode": 0, "message": "Received"}


def _load_payment_for_ipn(client, request_id: str) -> dict:
    response = (
        client.table("payments")
        .select("id,order_id,method,amount,status,payment_data")
        .eq("id", request_id)
        .limit(1)
        .execute()
    )
    payment = (response.data or [None])[0]
    if not payment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Payment not found",
        )
    return payment


def _validate_momo_ipn_payload(payload: dict, payment: dict) -> None:
    if payload.get("partnerCode") != settings.momo_partner_code:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid MoMo partnerCode",
        )
    if payment.get("method") != "momo":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Payment method is not MoMo",
        )

    payment_data = payment.get("payment_data") or {}
    if payload.get("orderId") != payment_data.get("momo_order_id"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="MoMo orderId does not match payment",
        )
    if payload.get("requestId") != payment_data.get("momo_request_id"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="MoMo requestId does not match payment",
        )

    payload_amount = _parse_decimal(payload.get("amount"), "amount")
    payment_amount = _parse_decimal(payment.get("amount"), "payment amount")
    if payload_amount != payment_amount:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="MoMo amount does not match payment",
        )


def _payment_is_expired(payment: dict) -> bool:
    payment_data = payment.get("payment_data") or {}
    expired_at = _parse_datetime(payment_data.get("expired_at"))
    return expired_at is not None and datetime.now(timezone.utc) > expired_at


def _validate_snapshot_amount(payment: dict) -> None:
    payment_data = payment.get("payment_data") or {}
    cart_snapshot = payment_data.get("cart_snapshot") or []
    snapshot_total = _calculate_snapshot_total(cart_snapshot)
    payment_amount = _parse_decimal(payment.get("amount"), "payment amount")
    payment_data_amount = _parse_decimal(
        payment_data.get("total_amount"),
        "payment_data total_amount",
    )
    if snapshot_total != payment_amount or payment_data_amount != payment_amount:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Payment snapshot amount does not match payment amount",
        )


def _update_payment_after_ipn(client, payment_id: str, update_payload: dict) -> None:
    (
        client.table("payments")
        .update(update_payload)
        .eq("id", payment_id)
        .execute()
    )


def expire_pending_momo_payments(client=None) -> int:
    client = client or get_service_supabase_client()
    response = (
        client.table("payments")
        .select("id,method,status,order_id,payment_data")
        .eq("method", "momo")
        .eq("status", "pending")
        .execute()
    )
    expired_count = 0
    for payment in response.data or []:
        if payment.get("order_id") or not _payment_is_expired(payment):
            continue
        payment_data = payment.get("payment_data") or {}
        _update_payment_after_ipn(
            client,
            payment["id"],
            {
                "status": "expired",
                "payment_data": {
                    **payment_data,
                    "expired_by": "expire_pending_momo_payments",
                },
                "updated_at": datetime.now(timezone.utc).isoformat(),
            },
        )
        expired_count += 1
    return expired_count


def _parse_datetime(value) -> datetime | None:
    if not value:
        return None
    try:
        normalized = str(value).replace("Z", "+00:00")
        parsed = datetime.fromisoformat(normalized)
        if parsed.tzinfo is None:
            return parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid payment expired_at",
        ) from exc


def _sync_order_status_after_payment_ipn(client, order_id: str, payment_status: str) -> None:
    if payment_status == "completed":
        order_status = "confirmed"
        (
            client.table("orders")
            .update(
                {
                    "status": order_status,
                    "updated_at": datetime.now(timezone.utc).isoformat(),
                }
            )
            .eq("id", order_id)
            .in_("status", ["pending"])
            .execute()
        )
        return

    if payment_status == "failed":
        if _order_has_active_or_completed_payment(client, order_id):
            return

        (
            client.table("orders")
            .update(
                {
                    "status": "cancelled",
                    "updated_at": datetime.now(timezone.utc).isoformat(),
                }
            )
            .eq("id", order_id)
            .in_("status", ["pending"])
            .execute()
        )


def _order_has_active_or_completed_payment(client, order_id: str) -> bool:
    response = (
        client.table("payments")
        .select("id")
        .eq("order_id", order_id)
        .in_("status", ["pending", "processing", "completed"])
        .limit(1)
        .execute()
    )
    return bool(response.data)


def _parse_int(value, field_name: str) -> int:
    try:
        return int(value)
    except (TypeError, ValueError) as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid MoMo {field_name}",
        ) from exc


def _parse_decimal(value, field_name: str) -> Decimal:
    try:
        return Decimal(str(value))
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid MoMo {field_name}",
        ) from exc


def _require_momo_settings() -> None:
    if not all(
        [
            settings.momo_partner_code,
            settings.momo_access_key,
            settings.momo_secret_key,
            settings.momo_create_endpoint,
        ]
    ):
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="MoMo configuration is missing",
        )


def _sign(raw_signature: str) -> str:
    return hmac.new(
        settings.momo_secret_key.encode("utf-8"),
        raw_signature.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()


def _verify_momo_result_signature(payload: dict) -> bool:
    raw_signature = (
        f"accessKey={settings.momo_access_key}"
        f"&amount={payload.get('amount')}"
        f"&extraData={payload.get('extraData', '')}"
        f"&message={payload.get('message')}"
        f"&orderId={payload.get('orderId')}"
        f"&orderInfo={payload.get('orderInfo')}"
        f"&orderType={payload.get('orderType')}"
        f"&partnerCode={payload.get('partnerCode')}"
        f"&payType={payload.get('payType')}"
        f"&requestId={payload.get('requestId')}"
        f"&responseTime={payload.get('responseTime')}"
        f"&resultCode={payload.get('resultCode')}"
        f"&transId={payload.get('transId')}"
    )
    expected = _sign(raw_signature)
    return hmac.compare_digest(expected, str(payload.get("signature", "")))


def _post_json(url: str, payload: dict) -> dict:
    request = Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urlopen(request, timeout=30) as response:
            return json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        message = exc.read().decode("utf-8", errors="replace")
        try:
            error_payload = json.loads(message)
        except json.JSONDecodeError:
            error_payload = {"response": message}
        response_status = (
            status.HTTP_400_BAD_REQUEST
            if exc.code == status.HTTP_400_BAD_REQUEST
            else status.HTTP_502_BAD_GATEWAY
        )
        raise HTTPException(
            status_code=response_status,
            detail={
                "message": "MoMo API returned an error",
                "status": exc.code,
                "response": error_payload,
            },
        ) from exc
    except (URLError, TimeoutError) as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Unable to connect to MoMo: {exc}",
        ) from exc


def _default_momo_redirect_url(ipn_url: str) -> str:
    parts = urlsplit(ipn_url)
    return urlunsplit((parts.scheme, parts.netloc, "/api/payments/momo/redirect", "", ""))


def _resolve_momo_redirect_url(ipn_url: str) -> str:
    if settings.momo_redirect_url:
        parts = urlsplit(settings.momo_redirect_url)
        if parts.scheme in {"http", "https"} and parts.netloc:
            return settings.momo_redirect_url
    return _default_momo_redirect_url(ipn_url)
