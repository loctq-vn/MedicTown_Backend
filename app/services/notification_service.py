import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path

import firebase_admin
from fastapi import HTTPException, status
from firebase_admin import credentials, messaging

from app.config import settings
from app.database import get_service_supabase_client
from app.schemas.notification_schema import DeviceTokenRequest


logger = logging.getLogger(__name__)


def _get_service_client():
    try:
        return get_service_supabase_client()
    except RuntimeError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Notification service is not configured",
        ) from exc


def register_device_token(
    user_id: str,
    payload: DeviceTokenRequest,
) -> None:
    client = _get_service_client()
    now = datetime.now(timezone.utc).isoformat()

    try:
        response = (
            client.table("device_tokens")
            .upsert(
                {
                    "user_id": user_id,
                    "token": payload.token,
                    "platform": "android",
                    "updated_at": now,
                },
                on_conflict="token",
            )
            .execute()
        )
    except Exception as exc:
        logger.exception("Unable to register notification device")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unable to register notification device",
        ) from exc

    if not response.data:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unable to register notification device",
        )


def unregister_device_token(
    user_id: str,
    payload: DeviceTokenRequest,
) -> None:
    client = _get_service_client()

    try:
        (
            client.table("device_tokens")
            .delete()
            .eq("user_id", user_id)
            .eq("token", payload.token)
            .execute()
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unable to unregister notification device",
        ) from exc
    

STATUS_MESSAGES = {
    "confirmed": ("Đơn hàng đã xác nhận", "Nhà thuốc đang chuẩn bị đơn hàng."),
    "shipping": ("Đơn hàng đang được giao", "Đơn hàng của bạn đang trên đường giao đến."),
    "completed": ("Giao hàng thành công", "Đơn hàng đã được giao thành công."),
    "cancelled": ("Đơn hàng đã hủy", "Đơn hàng của bạn đã bị hủy."),
}


def _initialize_firebase() -> None:
    try:
        firebase_admin.get_app()
        return
    except ValueError:
        pass

    path = settings.firebase_credentials_path
    if not path:
        raise RuntimeError("FIREBASE_CREDENTIALS_PATH is not configured")

    credential_path = Path(path).resolve()
    if not credential_path.is_file():
        raise RuntimeError(f"Firebase credential file not found: {credential_path}")

    firebase_admin.initialize_app(
        credentials.Certificate(str(credential_path))
    )

def _delete_device_token(client, token: str) -> None:
    try:
        (
            client.table("device_tokens")
            .delete()
            .eq("token", token)
            .execute()
        )
        logger.info("Removed invalid Firebase device token")
    except Exception:
        # Cleanup failure must not break the order-status request.
        logger.exception("Unable to remove invalid Firebase token")
        
def send_order_status_notification(order: dict) -> None:
    status_value = str(order.get("status") or "").lower()
    message_text = STATUS_MESSAGES.get(status_value)
    user_id = order.get("user_id")

    if not message_text or not user_id:
        return

    _initialize_firebase()
    client = get_service_supabase_client()

    response = (
        client.table("device_tokens")
        .select("token")
        .eq("user_id", user_id)
        .execute()
    )

    title, body = message_text
    for row in response.data or []:
        token = row.get("token")
        if not token:
            continue

        try:
            messaging.send(
                messaging.Message(
                    data={
                        "type": "order_status",
                        "order_id": str(order["id"]),
                        "status": status_value,
                        "title": title,
                        "body": body,
                    },
                    android=messaging.AndroidConfig(priority="high"),
                    token=token,
                )
            )

        except messaging.UnregisteredError:
            logger.warning(
                "Firebase rejected an unregistered token for user %s",
                user_id,
            )
            _delete_device_token(client, token)

        except Exception:
            logger.exception(
                "Unable to send FCM notification for order %s",
                order.get("id"),
            )

def delete_stale_device_tokens(max_age_days: int = 90) -> int:
    client = get_service_supabase_client()

    cutoff = (
        datetime.now(timezone.utc) - timedelta(days=max_age_days)
    ).isoformat()

    response = (
        client.table("device_tokens")
        .delete()
        .lt("updated_at", cutoff)
        .execute()
    )

    deleted = response.data or []

    logger.info(
        "Deleted %d device tokens older than %d days",
        len(deleted),
        max_age_days,
    )

    return len(deleted)
