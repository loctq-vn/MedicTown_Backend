from typing import Any

from fastapi import WebSocket
from starlette.concurrency import run_in_threadpool

from app.database import get_base_supabase_client, get_service_supabase_client
from app.services.shop_service import get_main_shop


class WebSocketAuthenticationError(Exception):
    pass


async def authenticate_chat_websocket(websocket: WebSocket) -> dict[str, Any]:
    token = _get_bearer_token(websocket)
    if not token:
        raise WebSocketAuthenticationError("Missing bearer token")

    try:
        response = await run_in_threadpool(
            get_base_supabase_client().auth.get_user,
            token,
        )
    except Exception as exc:
        raise WebSocketAuthenticationError("Invalid or expired token") from exc

    user = getattr(response, "user", None)
    if user is None:
        raise WebSocketAuthenticationError("Invalid or expired token")

    user_id = str(user.id)
    profile = await run_in_threadpool(_get_user_profile, user_id)
    role = (profile or {}).get("role")
    if role == "customer":
        return {
            "id": user_id,
            "email": user.email,
            "role": "customer",
            "access_token": token,
        }

    if role == "seller":
        shop = await run_in_threadpool(get_main_shop)
        if str(shop["owner_id"]) == user_id:
            return {
                "id": user_id,
                "email": user.email,
                "role": "seller",
                "access_token": token,
            }

    raise WebSocketAuthenticationError("Chat access denied")


def _get_bearer_token(websocket: WebSocket) -> str | None:
    authorization = websocket.headers.get("authorization")
    if not authorization:
        return None
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token.strip():
        return None
    return token.strip()


def _get_user_profile(user_id: str) -> dict | None:
    response = (
        get_service_supabase_client()
        .table("users")
        .select("id,role")
        .eq("id", user_id)
        .maybe_single()
        .execute()
    )
    return response.data if response else None
