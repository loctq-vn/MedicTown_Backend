import asyncio
from datetime import datetime, timezone
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from app.dependencies import get_current_user
from app.main import app
from app.routers import chat as chat_router
from app.websocket.auth import WebSocketAuthenticationError
from app.websocket.chat_manager import ChatConnectionManager, chat_connection_manager


class FakeWebSocket:
    def __init__(self, fail_send: bool = False):
        self.accepted = False
        self.events = []
        self.fail_send = fail_send

    async def accept(self):
        self.accepted = True

    async def send_json(self, event):
        if self.fail_send:
            raise RuntimeError("Disconnected")
        self.events.append(event)


def _message(conversation_id: str) -> dict:
    return {
        "id": str(uuid4()),
        "conversation_id": conversation_id,
        "sender_id": str(uuid4()),
        "sender_type": "customer",
        "content": "Hello",
        "message_type": "text",
        "client_message_id": str(uuid4()),
        "read_at": None,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "deleted_at": None,
    }


def test_connection_manager_sends_to_every_device_and_removes_failures():
    async def scenario():
        manager = ChatConnectionManager()
        first = FakeWebSocket()
        second = FakeWebSocket()
        failed = FakeWebSocket(fail_send=True)

        await manager.connect("user-1", first)
        await manager.connect("user-1", second)
        await manager.connect("user-1", failed)
        await manager.send_to_user("user-1", {"type": "test"})

        assert first.events == [{"type": "test"}]
        assert second.events == [{"type": "test"}]
        assert await manager.connection_count("user-1") == 2

    asyncio.run(scenario())


def test_send_message_emits_event_only_for_new_message(monkeypatch):
    conversation_id = str(uuid4())
    message = _message(conversation_id)
    sent_events = []

    async def capture_event(user_id, event):
        sent_events.append((user_id, event))

    monkeypatch.setattr(
        chat_router.chat_service,
        "send_message_with_delivery",
        lambda _user, _payload: (message, "recipient-1", True),
    )
    monkeypatch.setattr(
        chat_router.chat_connection_manager,
        "send_to_user",
        capture_event,
    )

    result = asyncio.run(
        chat_router.send_message(
            chat_router.ChatMessageCreate(
                conversation_id=conversation_id,
                client_message_id=uuid4(),
                content="Hello",
            ),
            {"id": "sender-1"},
        )
    )

    assert result == message
    assert sent_events[0][0] == "recipient-1"
    assert sent_events[0][1]["type"] == "chat.message.created"
    assert sent_events[0][1]["data"] == {
        "conversation_id": conversation_id,
        "message_id": message["id"],
    }

    sent_events.clear()
    monkeypatch.setattr(
        chat_router.chat_service,
        "send_message_with_delivery",
        lambda _user, _payload: (message, "recipient-1", False),
    )
    asyncio.run(
        chat_router.send_message(
            chat_router.ChatMessageCreate(
                conversation_id=conversation_id,
                client_message_id=uuid4(),
                content="Hello",
            ),
            {"id": "sender-1"},
        )
    )
    assert sent_events == []


def test_websocket_heartbeat_and_cleanup(monkeypatch):
    async def authenticate(_websocket):
        return {"id": "customer-1", "role": "customer"}

    monkeypatch.setattr(chat_router, "authenticate_chat_websocket", authenticate)

    with TestClient(app) as client:
        with client.websocket_connect(
            "/api/chat/ws",
            headers={"Authorization": "Bearer valid"},
        ) as websocket:
            websocket.send_json({"type": "ping"})
            assert websocket.receive_json()["type"] == "pong"

    assert asyncio.run(
        chat_connection_manager.connection_count("customer-1")
    ) == 0


def test_websocket_rejects_invalid_token(monkeypatch):
    async def reject(_websocket):
        raise WebSocketAuthenticationError("Invalid or expired token")

    monkeypatch.setattr(chat_router, "authenticate_chat_websocket", reject)

    with TestClient(app) as client:
        with pytest.raises(WebSocketDisconnect) as exc_info:
            with client.websocket_connect("/api/chat/ws"):
                pass

    assert exc_info.value.code == 1008


def test_rest_message_reaches_connected_recipient(monkeypatch):
    conversation_id = str(uuid4())
    message = _message(conversation_id)

    async def authenticate(_websocket):
        return {"id": "recipient-1", "role": "seller"}

    def current_user_override():
        return {"id": "sender-1"}

    monkeypatch.setattr(chat_router, "authenticate_chat_websocket", authenticate)
    monkeypatch.setattr(
        chat_router.chat_service,
        "send_message_with_delivery",
        lambda _user, _payload: (message, "recipient-1", True),
    )
    app.dependency_overrides[get_current_user] = current_user_override

    try:
        with TestClient(app) as client:
            with client.websocket_connect(
                "/api/chat/ws",
                headers={"Authorization": "Bearer valid"},
            ) as websocket:
                response = client.post(
                    "/api/chat/messages",
                    json={
                        "conversation_id": conversation_id,
                        "client_message_id": str(uuid4()),
                        "content": "Hello",
                    },
                )
                assert response.status_code == 201
                event = websocket.receive_json()
                assert event["type"] == "chat.message.created"
                assert event["data"]["message_id"] == message["id"]
    finally:
        app.dependency_overrides.clear()
