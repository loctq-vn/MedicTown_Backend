from types import SimpleNamespace

from app.schemas.auth_schema import AuthResponse, UserResponse
from app.schemas.cart_schema import CartItemCreate
from app.schemas.order_schema import Order, OrderCreate
from app.services import auth_service, cart_service, order_service, payment_service


def test_login_returns_auth_response(client, monkeypatch):
    def fake_login(payload):
        return AuthResponse(
            access_token="access",
            refresh_token="refresh",
            user=UserResponse(
                id="00000000-0000-0000-0000-000000000001",
                email=payload.email,
                name="User",
                role="customer",
            ),
        )

    monkeypatch.setattr(auth_service, "login", fake_login)

    response = client.post(
        "/api/auth/login",
        json={"email": "user@example.com", "password": "secret123"},
    )

    assert response.status_code == 200
    assert response.json()["access_token"] == "access"
    assert response.json()["user"]["email"] == "user@example.com"


def test_add_to_cart_uses_current_user(authenticated_client, monkeypatch):
    captured = {}

    def fake_add_to_cart(user_id, payload):
        captured["user_id"] = user_id
        captured["payload"] = payload
        return {
            "id": "10000000-0000-0000-0000-000000000001",
            "user_id": user_id,
            "product_id": payload.product_id,
            "quantity": payload.quantity,
        }

    monkeypatch.setattr(cart_service, "add_to_cart", fake_add_to_cart)

    response = authenticated_client.post(
        "/api/cart_items",
        json={
            "product_id": "20000000-0000-0000-0000-000000000001",
            "quantity": 2,
        },
    )

    assert response.status_code == 201
    assert captured["user_id"] == "00000000-0000-0000-0000-000000000001"
    assert isinstance(captured["payload"], CartItemCreate)
    assert response.json()["quantity"] == 2


def test_create_order_calls_rpc_and_attaches_momo(monkeypatch):
    rpc_params = {}

    class FakeRpc:
        data = [
            {
                "id": "30000000-0000-0000-0000-000000000001",
                "user_id": "00000000-0000-0000-0000-000000000001",
                "status": "pending",
                "total_amount": 10000,
                "shipping_name": "User",
                "shipping_phone": "0900000000",
                "shipping_address": "Address",
                "order_items": [],
                "payments": [
                    {
                        "id": "40000000-0000-0000-0000-000000000001",
                        "method": "momo",
                        "amount": 10000,
                        "status": "processing",
                    }
                ],
            }
        ]

        def execute(self):
            return self

    def fake_rpc(name, params):
        rpc_params["name"] = name
        rpc_params["params"] = params
        return FakeRpc()

    def fake_attach(order, payment, amount):
        assert order["id"] == "30000000-0000-0000-0000-000000000001"
        assert payment["id"] == "40000000-0000-0000-0000-000000000001"
        return {
            **payment,
            "status": "processing",
            "payment_data": {"payUrl": "https://momo.test/pay"},
        }

    monkeypatch.setattr(order_service.supabase, "rpc", fake_rpc)
    monkeypatch.setattr(payment_service, "attach_momo_checkout_data", fake_attach)

    orders = order_service.create_order(
        "00000000-0000-0000-0000-000000000001",
        OrderCreate(
            cart_item_ids=["50000000-0000-0000-0000-000000000001"],
            payment_method="momo",
            shipping_address="Address",
        ),
    )

    assert rpc_params["name"] == "create_order_transaction"
    assert rpc_params["params"]["p_payment_method"] == "momo"
    assert rpc_params["params"]["p_payment_status"] == "processing"
    assert orders[0]["payments"][0]["payment_data"]["payUrl"] == "https://momo.test/pay"


def test_list_orders_wraps_single_payment_relation(monkeypatch):
    class FakeQuery:
        def select(self, *_args):
            return self

        def eq(self, *_args):
            return self

        def order(self, *_args, **_kwargs):
            return self

        def execute(self):
            return SimpleNamespace(
                data=[
                    {
                        "id": "30000000-0000-0000-0000-000000000001",
                        "user_id": "00000000-0000-0000-0000-000000000001",
                        "status": "pending",
                        "total_amount": 10000,
                        "order_items": [],
                        "payments": {
                            "id": "40000000-0000-0000-0000-000000000001",
                            "method": "momo",
                            "amount": 10000,
                            "status": "processing",
                        },
                    }
                ]
            )

    monkeypatch.setattr(order_service.supabase, "table", lambda _table_name: FakeQuery())

    orders = order_service.list_orders("00000000-0000-0000-0000-000000000001")

    assert isinstance(orders[0]["payments"], list)
    assert orders[0]["payments"][0]["id"] == "40000000-0000-0000-0000-000000000001"
    Order.model_validate(orders[0])


def test_momo_ipn_updates_payment_and_order(monkeypatch):
    updates = []

    class FakeQuery:
        def __init__(self, table_name=None, data=None):
            self.table_name = table_name
            self.update_data = data

        def select(self, *_args):
            return self

        def update(self, data):
            updates.append((self.table_name, data))
            return FakeQuery(self.table_name, data)

        def eq(self, *_args):
            return self

        def in_(self, *_args):
            return self

        def limit(self, *_args):
            return self

        def execute(self):
            if self.table_name == "payments" and self.update_data is None:
                return SimpleNamespace(
                    data=[
                        {
                            "id": "40000000-0000-0000-0000-000000000001",
                            "order_id": "30000000-0000-0000-0000-000000000001",
                            "method": "momo",
                            "amount": 10000,
                            "status": "processing",
                            "payment_data": {
                                "momo_order_id": "MEDICTOWN-30000000-0000-0000-0000-000000000001",
                                "momo_request_id": "40000000-0000-0000-0000-000000000001",
                            },
                        }
                    ]
                )
            return SimpleNamespace(data=[self.update_data or {}])

    class FakeClient:
        def table(self, table_name):
            return FakeQuery(table_name)

    payload = {
        "partnerCode": "MOMO",
        "requestId": "40000000-0000-0000-0000-000000000001",
        "orderId": "MEDICTOWN-30000000-0000-0000-0000-000000000001",
        "amount": 10000,
        "resultCode": 0,
        "transId": "123456",
        "signature": "valid",
    }

    monkeypatch.setattr(payment_service, "_require_momo_settings", lambda: None)
    monkeypatch.setattr(payment_service, "_verify_momo_result_signature", lambda _payload: True)
    monkeypatch.setattr(payment_service, "get_service_supabase_client", lambda: FakeClient())
    monkeypatch.setattr(payment_service.settings, "momo_partner_code", "MOMO")

    response = payment_service.handle_momo_ipn(payload)

    assert response == {"resultCode": 0, "message": "Received"}
    assert ("payments",) == (updates[0][0],)
    assert updates[0][1]["status"] == "completed"
    assert updates[1][0] == "orders"
    assert updates[1][1]["status"] == "confirmed"
