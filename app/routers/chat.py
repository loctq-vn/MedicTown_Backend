from datetime import datetime, timezone
from uuid import UUID, uuid4

from fastapi import (
    APIRouter,
    Depends,
    Header,
    Query,
    Request,
    WebSocket,
    WebSocketDisconnect,
    status,
)
from starlette.concurrency import run_in_threadpool

from app.dependencies import get_current_user
from app.schemas.chat_schema import (
    ChatConversation,
    ChatMessage,
    ChatMessageCreate,
    ChatMessagePage,
    ChatReadRequest,
    ChatReadResult,
    SellerConversationItem,
)
from app.services import chat_service
from app.websocket.auth import (
    WebSocketAuthenticationError,
    authenticate_chat_websocket,
)
from app.websocket.chat_manager import chat_connection_manager

router = APIRouter()


@router.post(
    "/conversation",
    response_model=ChatConversation,
    status_code=status.HTTP_200_OK,
)
def get_or_create_conversation(
    current_user: dict = Depends(get_current_user),
) -> dict:
    return chat_service.get_or_create_conversation(current_user)


@router.get("/messages", response_model=ChatMessagePage)
def list_messages(
    conversation_id: UUID,
    before: datetime | None = None,
    before_id: UUID | None = None,
    after: datetime | None = None,
    after_id: UUID | None = None,
    limit: int = Query(default=30, ge=1, le=100),
    current_user: dict = Depends(get_current_user),
) -> dict:
    return chat_service.list_messages(
        current_user,
        str(conversation_id),
        before=before,
        before_id=str(before_id) if before_id else None,
        after=after,
        after_id=str(after_id) if after_id else None,
        limit=limit,
    )


@router.post("/images")
async def upload_chat_image(
    conversation_id: UUID,
    request: Request,
    filename: str | None = None,
    content_type: str | None = Header(default=None, alias="Content-Type"),
    current_user: dict = Depends(get_current_user),
) -> dict:
    content = await request.body()
    return await chat_service.upload_chat_image(
        current_user,
        str(conversation_id),
        content,
        content_type=content_type,
        filename=filename,
    )


@router.post(
    "/messages",
    response_model=ChatMessage,
    status_code=status.HTTP_201_CREATED,
)
async def send_message(
    payload: ChatMessageCreate,
    current_user: dict = Depends(get_current_user),
) -> dict:
    message, recipient_id, created = await run_in_threadpool(
        chat_service.send_message_with_delivery,
        current_user,
        payload,
    )
    if created:
        await chat_connection_manager.send_to_user(
            recipient_id,
            {
                "type": "chat.message.created",
                "event_id": str(uuid4()),
                "occurred_at": datetime.now(timezone.utc).isoformat(),
                "data": {
                    "conversation_id": message["conversation_id"],
                    "message_id": message["id"],
                },
            },
        )
    return message


@router.patch("/read", response_model=ChatReadResult)
def mark_messages_read(
    payload: ChatReadRequest,
    current_user: dict = Depends(get_current_user),
) -> dict:
    return chat_service.mark_messages_read(
        current_user,
        str(payload.conversation_id),
    )


@router.get(
    "/seller/conversations",
    response_model=list[SellerConversationItem],
)
def list_seller_conversations(
    current_user: dict = Depends(get_current_user),
) -> list[dict]:
    return chat_service.list_seller_conversations(current_user)


@router.websocket("/ws")
async def chat_websocket(websocket: WebSocket) -> None:
    try:
        current_user = await authenticate_chat_websocket(websocket)
    except WebSocketAuthenticationError as exc:
        await websocket.close(code=1008, reason=str(exc))
        return

    user_id = str(current_user["id"])
    await chat_connection_manager.connect(user_id, websocket)
    try:
        while True:
            event = await websocket.receive_json()
            if event.get("type") == "ping":
                await websocket.send_json(
                    {
                        "type": "pong",
                        "occurred_at": datetime.now(timezone.utc).isoformat(),
                    }
                )
    except WebSocketDisconnect:
        pass
    except Exception:
        await websocket.close(code=1003, reason="Invalid WebSocket event")
    finally:
        await chat_connection_manager.disconnect(user_id, websocket)
