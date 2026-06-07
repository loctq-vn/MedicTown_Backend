from datetime import datetime, timezone
from types import SimpleNamespace
from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.schemas.chat_schema import ChatMessageCreate
from app.services import chat_service


class InsertQuery:
    def __init__(self, row):
        self.row = row
        self.inserted = None

    def insert(self, data):
        self.inserted = data
        return self

    def execute(self):
        return SimpleNamespace(data=[self.row])


class UpdateQuery:
    def __init__(self, rows):
        self.rows = rows
        self.updated = None
        self.filters = []

    def update(self, data):
        self.updated = data
        return self

    def eq(self, column, value):
        self.filters.append(("eq", column, value))
        return self

    def is_(self, column, value):
        self.filters.append(("is", column, value))
        return self

    def execute(self):
        return SimpleNamespace(data=self.rows)


class SelectQuery:
    def __init__(self, rows):
        self.rows = rows
        self.limit_value = None
        self.filters = []
        self.orders = []

    def select(self, _columns):
        return self

    def eq(self, _column, _value):
        return self

    def is_(self, _column, _value):
        return self

    def lt(self, column, value):
        self.filters.append(("lt", column, value))
        return self

    def gt(self, column, value):
        self.filters.append(("gt", column, value))
        return self

    def or_(self, filters):
        self.filters.append(("or", filters))
        return self

    def order(self, column, **kwargs):
        self.orders.append((column, kwargs))
        return self

    def limit(self, value):
        self.limit_value = value
        return self

    def execute(self):
        return SimpleNamespace(data=self.rows)


def _message_payload():
    return ChatMessageCreate(
        conversation_id=uuid4(),
        client_message_id=uuid4(),
        content="  Xin chao shop  ",
    )


def test_message_payload_rejects_identity_fields():
    with pytest.raises(ValidationError):
        ChatMessageCreate(
            conversation_id=uuid4(),
            client_message_id=uuid4(),
            content="Hello",
            sender_id=str(uuid4()),
            sender_type="seller",
            shop_id=str(uuid4()),
        )


def test_conversation_is_created_by_backend_for_main_shop(monkeypatch):
    user_id = str(uuid4())
    shop_id = str(uuid4())
    created = {
        "id": str(uuid4()),
        "shop_id": shop_id,
        "customer_id": user_id,
        "last_message_at": None,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    query = InsertQuery(created)
    service_client = SimpleNamespace(table=lambda _name: query)

    monkeypatch.setattr(chat_service, "_require_customer", lambda _user_id: None)
    monkeypatch.setattr(
        chat_service,
        "_find_customer_conversation",
        lambda _user_id: None,
    )
    monkeypatch.setattr(chat_service, "get_main_shop", lambda: {"id": shop_id})
    monkeypatch.setattr(
        chat_service,
        "get_service_supabase_client",
        lambda: service_client,
    )

    result = chat_service.get_or_create_conversation({"id": user_id})

    assert result == created
    assert query.inserted == {
        "shop_id": shop_id,
        "customer_id": user_id,
    }


def test_send_message_derives_customer_identity(monkeypatch):
    payload = _message_payload()
    user_id = str(uuid4())
    conversation = {
        "id": str(payload.conversation_id),
        "customer_id": user_id,
        "shop_id": str(uuid4()),
    }
    created = {
        "id": str(uuid4()),
        "conversation_id": str(payload.conversation_id),
        "sender_id": user_id,
        "sender_type": "customer",
        "content": payload.content,
        "message_type": "text",
        "client_message_id": str(payload.client_message_id),
        "read_at": None,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "deleted_at": None,
    }
    query = InsertQuery(created)

    monkeypatch.setattr(
        chat_service,
        "_get_accessible_conversation",
        lambda _user_id, _conversation_id: conversation,
    )
    monkeypatch.setattr(
        chat_service,
        "_find_message_by_client_id",
        lambda _sender_id, _client_message_id: None,
    )
    monkeypatch.setattr(
        chat_service,
        "get_main_shop",
        lambda: {
            "id": conversation["shop_id"],
            "owner_id": "seller-1",
        },
    )
    monkeypatch.setattr(chat_service.supabase, "table", lambda _name: query)

    result = chat_service.send_message({"id": user_id}, payload)

    assert result == created
    assert query.inserted["sender_id"] == user_id
    assert query.inserted["sender_type"] == "customer"
    assert query.inserted["content"] == "Xin chao shop"


def test_send_message_retry_returns_existing_without_insert(monkeypatch):
    payload = _message_payload()
    user_id = str(uuid4())
    conversation = {
        "id": str(payload.conversation_id),
        "customer_id": user_id,
        "shop_id": str(uuid4()),
    }
    existing = {
        "id": str(uuid4()),
        "conversation_id": str(payload.conversation_id),
        "sender_id": user_id,
        "client_message_id": str(payload.client_message_id),
    }

    monkeypatch.setattr(
        chat_service,
        "_get_accessible_conversation",
        lambda _user_id, _conversation_id: conversation,
    )
    monkeypatch.setattr(
        chat_service,
        "_find_message_by_client_id",
        lambda _sender_id, _client_message_id: existing,
    )
    monkeypatch.setattr(
        chat_service,
        "get_main_shop",
        lambda: {
            "id": conversation["shop_id"],
            "owner_id": "seller-1",
        },
    )
    monkeypatch.setattr(
        chat_service.supabase,
        "table",
        lambda _name: pytest.fail("Retry must not insert another message"),
    )

    assert chat_service.send_message({"id": user_id}, payload) == existing


def test_customer_marks_only_seller_messages_read(monkeypatch):
    conversation_id = str(uuid4())
    user_id = str(uuid4())
    conversation = {
        "id": conversation_id,
        "customer_id": user_id,
        "shop_id": str(uuid4()),
    }
    query = UpdateQuery([{"id": "message-1"}, {"id": "message-2"}])

    monkeypatch.setattr(
        chat_service,
        "_get_accessible_conversation",
        lambda _user_id, _conversation_id: conversation,
    )
    monkeypatch.setattr(chat_service.supabase, "table", lambda _name: query)

    result = chat_service.mark_messages_read({"id": user_id}, conversation_id)

    assert result["updated_count"] == 2
    assert ("eq", "sender_type", "seller") in query.filters
    assert ("is", "read_at", "null") in query.filters
    assert query.updated["read_at"]


def test_message_page_is_oldest_to_newest_with_cursor(monkeypatch):
    conversation_id = str(uuid4())
    rows = [
        {"id": "3", "created_at": "2026-06-07T03:00:00+00:00"},
        {"id": "2", "created_at": "2026-06-07T02:00:00+00:00"},
        {"id": "1", "created_at": "2026-06-07T01:00:00+00:00"},
    ]
    query = SelectQuery(rows)

    monkeypatch.setattr(
        chat_service,
        "_get_accessible_conversation",
        lambda _user_id, _conversation_id: {"id": conversation_id},
    )
    monkeypatch.setattr(chat_service.supabase, "table", lambda _name: query)

    result = chat_service.list_messages(
        {"id": str(uuid4())},
        conversation_id,
        limit=2,
    )

    assert [message["id"] for message in result["items"]] == ["2", "3"]
    assert result["next_cursor"] == rows[1]["created_at"]
    assert result["next_cursor_id"] == rows[1]["id"]
    assert query.limit_value == 3


def test_message_sync_returns_newer_messages_in_ascending_order(monkeypatch):
    conversation_id = str(uuid4())
    after = datetime(2026, 6, 7, 1, 0, tzinfo=timezone.utc)
    after_id = str(uuid4())
    rows = [
        {"id": "2", "created_at": "2026-06-07T02:00:00+00:00"},
        {"id": "3", "created_at": "2026-06-07T03:00:00+00:00"},
        {"id": "4", "created_at": "2026-06-07T04:00:00+00:00"},
    ]
    query = SelectQuery(rows)

    monkeypatch.setattr(
        chat_service,
        "_get_accessible_conversation",
        lambda _user_id, _conversation_id: {"id": conversation_id},
    )
    monkeypatch.setattr(chat_service.supabase, "table", lambda _name: query)

    result = chat_service.list_messages(
        {"id": str(uuid4())},
        conversation_id,
        after=after,
        after_id=after_id,
        limit=2,
    )

    assert [message["id"] for message in result["items"]] == ["2", "3"]
    assert result["next_cursor"] == rows[1]["created_at"]
    assert result["next_cursor_id"] == rows[1]["id"]
    assert query.orders == [("created_at", {}), ("id", {})]
    assert query.limit_value == 3
    assert any(item[0] == "or" for item in query.filters)


def test_message_page_rejects_before_and_after_together(monkeypatch):
    monkeypatch.setattr(
        chat_service,
        "_get_accessible_conversation",
        lambda _user_id, _conversation_id: {"id": "conversation-1"},
    )

    with pytest.raises(Exception) as exc_info:
        chat_service.list_messages(
            {"id": str(uuid4())},
            "conversation-1",
            before=datetime.now(timezone.utc),
            after=datetime.now(timezone.utc),
        )

    assert exc_info.value.status_code == 400
