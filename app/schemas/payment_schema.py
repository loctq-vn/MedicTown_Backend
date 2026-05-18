from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict


class PaymentCreate(BaseModel):
    order_id: str
    method: str
    amount: float
    transaction_id: str | None = None
    payment_data: dict[str, Any] | None = None


class Payment(BaseModel):
    id: str
    order_id: str
    method: str
    amount: float
    status: str = "pending"
    transaction_id: str | None = None
    payment_data: dict[str, Any] | None = None

    model_config = ConfigDict(from_attributes=True, extra="allow")
