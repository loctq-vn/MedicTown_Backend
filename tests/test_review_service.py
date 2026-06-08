from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.schemas.review_schema import ReviewCreate
from app.services import review_service


class FakeQuery:
    def __init__(self, client, table_name):
        self.client = client
        self.table_name = table_name
        self.inserted = None

    def select(self, _columns):
        return self

    def eq(self, _column, _value):
        return self

    def maybe_single(self):
        return self

    def insert(self, data):
        self.inserted = data
        self.client.inserted_rows.append((self.table_name, data))
        return self

    def execute(self):
        if self.inserted is not None:
            return SimpleNamespace(data=[self.client.created_review])
        return self.client.select_responses[self.table_name].pop(0)


class FakeSupabase:
    def __init__(self, select_responses, created_review=None):
        self.select_responses = {
            table_name: list(responses)
            for table_name, responses in select_responses.items()
        }
        self.created_review = created_review
        self.inserted_rows = []

    def table(self, table_name):
        return FakeQuery(self, table_name)


def test_create_review_allows_missing_existing_review_response(monkeypatch):
    user_id = "user-1"
    product_id = "product-1"
    order_item_id = "order-item-1"
    created_review = {
        "id": "review-1",
        "product_id": product_id,
        "order_item_id": order_item_id,
        "user_id": user_id,
        "rating": 5,
        "comment": "Good",
        "images": None,
    }
    fake_supabase = FakeSupabase(
        {
            "order_items": [
                SimpleNamespace(
                    data={
                        "id": order_item_id,
                        "order_id": "order-1",
                        "product_id": product_id,
                    },
                ),
            ],
            "orders": [
                SimpleNamespace(
                    data={
                        "id": "order-1",
                        "user_id": user_id,
                        "status": "completed",
                    },
                ),
            ],
            "reviews": [None],
        },
        created_review=created_review,
    )
    monkeypatch.setattr(review_service.supabase, "table", fake_supabase.table)

    result = review_service.create_review(
        user_id,
        ReviewCreate(
            product_id=product_id,
            order_item_id=order_item_id,
            rating=5,
            comment="Good",
        ),
    )

    assert result["images"] == []
    assert fake_supabase.inserted_rows == [
        (
            "reviews",
            {
                "product_id": product_id,
                "order_item_id": order_item_id,
                "user_id": user_id,
                "rating": 5,
                "comment": "Good",
            },
        ),
    ]


def test_create_review_rejects_existing_review(monkeypatch):
    user_id = "user-1"
    product_id = "product-1"
    order_item_id = "order-item-1"
    fake_supabase = FakeSupabase(
        {
            "order_items": [
                SimpleNamespace(
                    data={
                        "id": order_item_id,
                        "order_id": "order-1",
                        "product_id": product_id,
                    },
                ),
            ],
            "orders": [
                SimpleNamespace(
                    data={
                        "id": "order-1",
                        "user_id": user_id,
                        "status": "completed",
                    },
                ),
            ],
            "reviews": [SimpleNamespace(data={"id": "review-1"})],
        },
    )
    monkeypatch.setattr(review_service.supabase, "table", fake_supabase.table)

    with pytest.raises(HTTPException) as exc_info:
        review_service.create_review(
            user_id,
            ReviewCreate(
                product_id=product_id,
                order_item_id=order_item_id,
                rating=5,
            ),
        )

    assert exc_info.value.status_code == 409
    assert fake_supabase.inserted_rows == []
