import hashlib
import hmac
import json
from datetime import datetime, timezone
from decimal import Decimal
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from urllib.parse import urlsplit, urlunsplit
from uuid import uuid4

from fastapi import HTTPException, status

from app.config import settings
from app.database import get_service_supabase_client, supabase


MOMO_SUCCESS_CODE = 0


def normalize_payment_method(payment_method: str | None) -> str:
    normalized = (payment_method or "").strip().lower()
    aliases = {
        "cod": "cash",
        "cash": "cash",
        "momo": "momo",
        "wallet": "wallet",
        "vnpay": "vnpay",
    }
    method = aliases.get(normalized)
    if not method:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Unsupported payment method",
        )
    return method


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


def create_momo_checkout_data(order: dict, payment_id: str, amount_value: Decimal) -> tuple[dict, str]:
    _require_momo_settings()

    amount = int(amount_value)
    if amount < 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="MoMo payment amount must be greater than or equal to 0 VND",
        )

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

    result_code = _parse_int(payload.get("resultCode"), "resultCode")
    payment_status = "completed" if result_code == MOMO_SUCCESS_CODE else "failed"
    current_payment_data = payment.get("payment_data") or {}
    merged_payment_data = {
        **current_payment_data,
        "momo_ipn_payload": payload,
    }
    update_payload = {
        "status": payment_status,
        "transaction_id": str(payload.get("transId")) if payload.get("transId") else None,
        "payment_data": merged_payment_data,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    if payment_status == "completed":
        update_payload["paid_at"] = datetime.now(timezone.utc).isoformat()

    (
        client.table("payments")
        .update(update_payload)
        .eq("id", request_id)
        .execute()
    )
    _sync_order_status_after_payment_ipn(client, payment["order_id"], payment_status)
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


def _sync_order_status_after_payment_ipn(client, order_id: str, payment_status: str) -> None:
    if payment_status == "completed":
        order_status = "confirmed"
        response = (
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
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail={
                "message": "MoMo API returned an error",
                "status": exc.code,
                "response": message,
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
