from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field


class DirectOrderItemCreate(BaseModel):
    product_id: str
    quantity: int = Field(gt=0)


class OrderCreate(BaseModel):
    cart_item_ids: list[str] = Field(default_factory=list)
    direct_items: list[DirectOrderItemCreate] = Field(default_factory=list)
    payment_method: str | None = None
    shipping_address: str | None = None
    note: str | None = None

    model_config = ConfigDict(extra="ignore")


class OrderItem(BaseModel):
    id: str | None = None
    order_id: str | None = None
    product_id: str
    product_name: str | None = None
    product_image: str | None = None
    price: float = 0
    quantity: int

    model_config = ConfigDict(from_attributes=True, extra="allow")


class Order(BaseModel):
    id: str
    user_id: str
    status: str = "pending"
    payment_method: str | None = None
    total_amount: float = 0
    prescription_url: str | None = None
    note: str | None = None
    shipping_name: str | None = None
    shipping_phone: str | None = None
    shipping_address: str | None = None
    shop_id: str | None = None
    order_items: list[OrderItem] = Field(default_factory=list)
    created_at: datetime | None = None
    updated_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True, extra="allow")
