import importlib
import os
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from supabase import create_client

from app.config import settings
from app.database import create_user_supabase_client, get_service_supabase_client


pytestmark = pytest.mark.skipif(
    os.getenv("RUN_SUPABASE_INTEGRATION") != "1",
    reason="Set RUN_SUPABASE_INTEGRATION=1 to run live Supabase chat tests",
)


def _create_test_user(admin, prefix: str, role: str) -> dict:
    unique = uuid4().hex
    email = f"medictown-{prefix}-{unique}@gmail.com"
    password = f"ChatTest-{unique[:12]}!"
    name = f"Chat test {prefix}"
    response = admin.create_user(
        {
            "email": email,
            "password": password,
            "email_confirm": True,
            "user_metadata": {
                "name": name,
                "full_name": name,
                "phone": "0900000000",
                "role": role,
            },
        }
    )
    return {
        "id": str(response.user.id),
        "email": email,
        "password": password,
        "name": name,
        "role": role,
    }


def _login(user: dict) -> str:
    client = create_client(settings.supabase_url, settings.supabase_anon_key)
    response = client.auth.sign_in_with_password(
        {
            "email": user["email"],
            "password": user["password"],
        }
    )
    return response.session.access_token


def _headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def test_chat_persistence_and_isolation_with_live_supabase():
    service = get_service_supabase_client()
    admin = service.auth.admin
    original_main_shop_id = settings.main_shop_id
    created_user_ids: list[str] = []
    shop_id = str(uuid4())

    try:
        customer_a = _create_test_user(admin, "customer-a", "customer")
        created_user_ids.append(customer_a["id"])
        customer_b = _create_test_user(admin, "customer-b", "customer")
        created_user_ids.append(customer_b["id"])
        seller = _create_test_user(admin, "seller", "seller")
        created_user_ids.append(seller["id"])

        service.table("users").upsert(
            [
                {
                    "id": user["id"],
                    "email": user["email"],
                    "name": user["name"],
                    "role": user["role"],
                }
                for user in (customer_a, customer_b, seller)
            ]
        ).execute()
        service.table("shops").insert(
            {
                "id": shop_id,
                "owner_id": seller["id"],
                "name": "Chat integration test shop",
                "is_active": True,
            }
        ).execute()
        settings.main_shop_id = UUID(shop_id)

        customer_a_token = _login(customer_a)
        customer_b_token = _login(customer_b)
        seller_token = _login(seller)

        from app.main import app

        customer_message_client_id = str(uuid4())
        seller_message_client_id = str(uuid4())

        with TestClient(app) as client:
            conversation_response = client.post(
                "/api/chat/conversation",
                headers=_headers(customer_a_token),
            )
            assert conversation_response.status_code == 200
            conversation = conversation_response.json()
            conversation_id = conversation["id"]
            assert conversation["customer_id"] == customer_a["id"]
            assert conversation["shop_id"] == shop_id

            with client.websocket_connect(
                "/api/chat/ws",
                headers=_headers(seller_token),
            ) as seller_websocket:
                customer_send_response = client.post(
                    "/api/chat/messages",
                    headers=_headers(customer_a_token),
                    json={
                        "conversation_id": conversation_id,
                        "client_message_id": customer_message_client_id,
                        "content": "Customer A integration message",
                    },
                )
                assert customer_send_response.status_code == 201
                customer_message = customer_send_response.json()
                assert customer_message["sender_type"] == "customer"
                seller_event = seller_websocket.receive_json()
                assert seller_event["type"] == "chat.message.created"
                assert seller_event["data"]["message_id"] == customer_message["id"]

            duplicate_response = client.post(
                "/api/chat/messages",
                headers=_headers(customer_a_token),
                json={
                    "conversation_id": conversation_id,
                    "client_message_id": customer_message_client_id,
                    "content": "Customer A integration message",
                },
            )
            assert duplicate_response.status_code == 201
            assert duplicate_response.json()["id"] == customer_message["id"]

            seller_list_response = client.get(
                "/api/chat/seller/conversations",
                headers=_headers(seller_token),
            )
            assert seller_list_response.status_code == 200
            seller_items = seller_list_response.json()
            seller_item = next(
                item
                for item in seller_items
                if item["conversation"]["id"] == conversation_id
            )
            assert seller_item["unread_count"] == 1
            assert seller_item["last_message"]["id"] == customer_message["id"]

            seller_history_response = client.get(
                "/api/chat/messages",
                headers=_headers(seller_token),
                params={"conversation_id": conversation_id},
            )
            assert seller_history_response.status_code == 200
            assert customer_message["id"] in {
                item["id"]
                for item in seller_history_response.json()["items"]
            }

            seller_read_response = client.patch(
                "/api/chat/read",
                headers=_headers(seller_token),
                json={"conversation_id": conversation_id},
            )
            assert seller_read_response.status_code == 200
            assert seller_read_response.json()["updated_count"] == 1

            with client.websocket_connect(
                "/api/chat/ws",
                headers=_headers(customer_a_token),
            ) as customer_websocket:
                seller_send_response = client.post(
                    "/api/chat/messages",
                    headers=_headers(seller_token),
                    json={
                        "conversation_id": conversation_id,
                        "client_message_id": seller_message_client_id,
                        "content": "Seller integration reply",
                    },
                )
                assert seller_send_response.status_code == 201
                seller_message = seller_send_response.json()
                assert seller_message["sender_type"] == "seller"
                customer_event = customer_websocket.receive_json()
                assert customer_event["type"] == "chat.message.created"
                assert customer_event["data"]["message_id"] == seller_message["id"]

            customer_history_response = client.get(
                "/api/chat/messages",
                headers=_headers(customer_a_token),
                params={"conversation_id": conversation_id},
            )
            assert customer_history_response.status_code == 200
            history_ids = {
                item["id"]
                for item in customer_history_response.json()["items"]
            }
            assert customer_message["id"] in history_ids
            assert seller_message["id"] in history_ids

            customer_read_response = client.patch(
                "/api/chat/read",
                headers=_headers(customer_a_token),
                json={"conversation_id": conversation_id},
            )
            assert customer_read_response.status_code == 200
            assert customer_read_response.json()["updated_count"] == 1

            for method, path, kwargs in (
                (
                    client.get,
                    "/api/chat/messages",
                    {"params": {"conversation_id": conversation_id}},
                ),
                (
                    client.post,
                    "/api/chat/messages",
                    {
                        "json": {
                            "conversation_id": conversation_id,
                            "client_message_id": str(uuid4()),
                            "content": "Customer B must not send this",
                        }
                    },
                ),
                (
                    client.patch,
                    "/api/chat/read",
                    {"json": {"conversation_id": conversation_id}},
                ),
            ):
                forbidden_response = method(
                    path,
                    headers=_headers(customer_b_token),
                    **kwargs,
                )
                assert forbidden_response.status_code == 404

        import app.main as app_main

        restarted_app = importlib.reload(app_main).app
        with TestClient(restarted_app) as restarted_client:
            persisted_response = restarted_client.get(
                "/api/chat/messages",
                headers=_headers(customer_a_token),
                params={"conversation_id": conversation_id},
            )
            assert persisted_response.status_code == 200
            persisted_ids = {
                item["id"]
                for item in persisted_response.json()["items"]
            }
            assert customer_message["id"] in persisted_ids
            assert seller_message["id"] in persisted_ids

        stored_messages = (
            service.table("chat_messages")
            .select("id,client_message_id,read_at")
            .eq("conversation_id", conversation_id)
            .execute()
            .data
            or []
        )
        assert len(stored_messages) == 2
        assert all(message["read_at"] is not None for message in stored_messages)
        assert sum(
            message["client_message_id"] == customer_message_client_id
            for message in stored_messages
        ) == 1

        customer_b_client = create_user_supabase_client(customer_b_token)
        hidden_messages = (
            customer_b_client.table("chat_messages")
            .select("id")
            .eq("conversation_id", conversation_id)
            .execute()
            .data
            or []
        )
        assert hidden_messages == []
    finally:
        settings.main_shop_id = original_main_shop_id
        if created_user_ids:
            service.table("chat_messages").delete().in_(
                "sender_id",
                created_user_ids,
            ).execute()
            service.table("chat_conversations").delete().in_(
                "customer_id",
                created_user_ids,
            ).execute()
        service.table("shops").delete().eq("id", shop_id).execute()
        if created_user_ids:
            service.table("users").delete().in_("id", created_user_ids).execute()
        for user_id in created_user_ids:
            admin.delete_user(user_id)
