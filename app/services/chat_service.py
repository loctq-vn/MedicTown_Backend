from datetime import datetime, timezone
from uuid import uuid4

from fastapi import HTTPException, status
from postgrest.exceptions import APIError

from app.config import settings
from app.database import get_service_supabase_client, supabase
from app.schemas.chat_schema import ChatMessageCreate
from app.services.shop_service import get_main_shop, require_main_shop_owner
from app.services.upload_validation import validate_image_upload


def get_or_create_conversation(current_user: dict) -> dict:
    user_id = str(current_user["id"])
    _require_customer(user_id)

    existing = _find_customer_conversation(user_id)
    if existing:
        return existing

    shop = get_main_shop()
    data = {
        "shop_id": str(shop["id"]),
        "customer_id": user_id,
    }
    service_client = get_service_supabase_client()
    try:
        response = service_client.table("chat_conversations").insert(data).execute()
    except APIError as exc:
        if _api_error_code(exc) == "23505":
            existing = _find_customer_conversation(user_id)
            if existing:
                return existing
        raise

    conversation = (response.data or [None])[0]
    if not conversation:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unable to create chat conversation",
        )
    return conversation


def list_messages(
    current_user: dict,
    conversation_id: str,
    before: datetime | None = None,
    before_id: str | None = None,
    after: datetime | None = None,
    after_id: str | None = None,
    limit: int = 30,
) -> dict:
    _get_accessible_conversation(str(current_user["id"]), conversation_id)
    if before and after:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Use either before or after, not both",
        )

    query = (
        supabase.table("chat_messages")
        .select("*")
        .eq("conversation_id", conversation_id)
        .is_("deleted_at", "null")
    )
    if before and before_id:
        query = query.or_(
            f"created_at.lt.{before.isoformat()},"
            f"and(created_at.eq.{before.isoformat()},id.lt.{before_id})"
        )
    elif before:
        query = query.lt("created_at", before.isoformat())

    if after and after_id:
        query = query.or_(
            f"created_at.gt.{after.isoformat()},"
            f"and(created_at.eq.{after.isoformat()},id.gt.{after_id})"
        )
    elif after:
        query = query.gt("created_at", after.isoformat())

    if after:
        response = (
            query.order("created_at")
            .order("id")
            .limit(limit + 1)
            .execute()
        )
        rows = response.data or []
        has_more = len(rows) > limit
        rows = rows[:limit]
        return {
            "items": rows,
            "next_cursor": rows[-1]["created_at"] if has_more and rows else None,
            "next_cursor_id": rows[-1]["id"] if has_more and rows else None,
        }

    response = (
        query.order("created_at", desc=True)
        .order("id", desc=True)
        .limit(limit + 1)
        .execute()
    )
    rows = response.data or []
    has_more = len(rows) > limit
    rows = rows[:limit]
    next_cursor = rows[-1]["created_at"] if has_more and rows else None

    return {
        "items": list(reversed(rows)),
        "next_cursor": next_cursor,
        "next_cursor_id": rows[-1]["id"] if has_more and rows else None,
    }


def send_message(current_user: dict, payload: ChatMessageCreate) -> dict:
    message, _, _ = send_message_with_delivery(current_user, payload)
    return message


def send_message_with_delivery(
    current_user: dict,
    payload: ChatMessageCreate,
) -> tuple[dict, str, bool]:
    user_id = str(current_user["id"])
    conversation_id = str(payload.conversation_id)
    conversation = _get_accessible_conversation(user_id, conversation_id)
    sender_type = _resolve_sender_type(user_id, conversation)
    recipient_id = _resolve_recipient_id(sender_type, conversation)
    client_message_id = str(payload.client_message_id)

    existing = _find_message_by_client_id(user_id, client_message_id)
    if existing:
        if existing.get("conversation_id") != conversation_id:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="client_message_id is already used in another conversation",
            )
        return existing, recipient_id, False

    data = {
        "conversation_id": conversation_id,
        "sender_id": user_id,
        "sender_type": sender_type,
        "content": payload.content,
        "message_type": payload.message_type,
        "metadata": payload.metadata,
        "client_message_id": client_message_id,
    }
    try:
        response = supabase.table("chat_messages").insert(data).execute()
    except APIError as exc:
        if _api_error_code(exc) == "23505":
            existing = _find_message_by_client_id(user_id, client_message_id)
            if existing and existing.get("conversation_id") == conversation_id:
                return existing, recipient_id, False
        raise

    message = (response.data or [None])[0]
    if not message:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unable to send chat message",
        )
    return message, recipient_id, True


async def upload_chat_image(
    current_user: dict,
    conversation_id: str,
    content: bytes,
    content_type: str | None = None,
    filename: str | None = None,
) -> dict:
    _get_accessible_conversation(str(current_user["id"]), conversation_id)
    extension, content_type = validate_image_upload(content, content_type, filename)
    file_path = f"chat/{conversation_id}/upload_{uuid4().hex}.{extension}"

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
            detail="Unable to upload chat image",
        ) from exc

    return {
        "path": file_path,
        "url": public_url,
        "mime_type": content_type,
    }


def mark_messages_read(current_user: dict, conversation_id: str) -> dict:
    user_id = str(current_user["id"])
    conversation = _get_accessible_conversation(user_id, conversation_id)
    sender_type = _resolve_sender_type(user_id, conversation)
    unread_sender_type = "seller" if sender_type == "customer" else "customer"
    read_at = datetime.now(timezone.utc)

    response = (
        supabase.table("chat_messages")
        .update({"read_at": read_at.isoformat()})
        .eq("conversation_id", conversation_id)
        .eq("sender_type", unread_sender_type)
        .is_("read_at", "null")
        .is_("deleted_at", "null")
        .execute()
    )
    return {
        "updated_count": len(response.data or []),
        "read_at": read_at,
    }


def list_seller_conversations(current_user: dict) -> list[dict]:
    user_id = str(current_user["id"])
    shop = require_main_shop_owner(user_id)
    shop_id = str(shop["id"])

    response = (
        supabase.table("chat_conversations")
        .select("*")
        .eq("shop_id", shop_id)
        .order("last_message_at", desc=True, nullsfirst=False)
        .order("created_at", desc=True)
        .execute()
    )
    conversations = response.data or []
    if not conversations:
        return []

    service_client = get_service_supabase_client()
    customer_ids = [conversation["customer_id"] for conversation in conversations]
    customer_response = (
        service_client.table("users")
        .select("id,name,avatar_url")
        .in_("id", customer_ids)
        .execute()
    )
    customers = {
        customer["id"]: customer
        for customer in customer_response.data or []
    }

    result = []
    for conversation in conversations:
        conversation_id = conversation["id"]
        last_message_response = (
            service_client.table("chat_messages")
            .select("*")
            .eq("conversation_id", conversation_id)
            .is_("deleted_at", "null")
            .order("created_at", desc=True)
            .order("id", desc=True)
            .limit(1)
            .execute()
        )
        unread_response = (
            service_client.table("chat_messages")
            .select("id", count="exact")
            .eq("conversation_id", conversation_id)
            .eq("sender_type", "customer")
            .is_("read_at", "null")
            .is_("deleted_at", "null")
            .execute()
        )
        customer = customers.get(conversation["customer_id"]) or {
            "id": conversation["customer_id"],
            "name": "Khach hang",
            "avatar_url": None,
        }
        result.append(
            {
                "conversation": conversation,
                "customer": customer,
                "last_message": (last_message_response.data or [None])[0],
                "unread_count": unread_response.count
                if unread_response.count is not None
                else len(unread_response.data or []),
            }
        )
    return result


def _require_customer(user_id: str) -> None:
    response = (
        supabase.table("users")
        .select("id,role")
        .eq("id", user_id)
        .maybe_single()
        .execute()
    )
    if not response.data or response.data.get("role") != "customer":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Customer access required",
        )


def _find_customer_conversation(user_id: str) -> dict | None:
    response = (
        supabase.table("chat_conversations")
        .select("*")
        .eq("customer_id", user_id)
        .maybe_single()
        .execute()
    )
    return response.data if response else None


def _get_accessible_conversation(user_id: str, conversation_id: str) -> dict:
    response = (
        supabase.table("chat_conversations")
        .select("*")
        .eq("id", conversation_id)
        .maybe_single()
        .execute()
    )
    conversation = response.data if response else None
    if not conversation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Chat conversation not found",
        )

    if str(conversation["customer_id"]) == user_id:
        return conversation

    shop = get_main_shop()
    if (
        str(shop["id"]) == str(conversation["shop_id"])
        and str(shop["owner_id"]) == user_id
    ):
        return conversation

    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail="Chat conversation not found",
    )


def _resolve_sender_type(user_id: str, conversation: dict) -> str:
    if str(conversation["customer_id"]) == user_id:
        return "customer"

    shop = get_main_shop()
    if (
        str(shop["id"]) == str(conversation["shop_id"])
        and str(shop["owner_id"]) == user_id
    ):
        return "seller"

    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail="Chat conversation not found",
    )


def _resolve_recipient_id(sender_type: str, conversation: dict) -> str:
    if sender_type == "seller":
        return str(conversation["customer_id"])

    shop = get_main_shop()
    if str(shop["id"]) != str(conversation["shop_id"]):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Chat conversation not found",
        )
    return str(shop["owner_id"])


def _find_message_by_client_id(
    sender_id: str,
    client_message_id: str,
) -> dict | None:
    response = (
        supabase.table("chat_messages")
        .select("*")
        .eq("sender_id", sender_id)
        .eq("client_message_id", client_message_id)
        .maybe_single()
        .execute()
    )
    return response.data if response else None


def _api_error_code(exc: APIError) -> str | None:
    if exc.args and isinstance(exc.args[0], dict):
        return exc.args[0].get("code")
    return getattr(exc, "code", None)
