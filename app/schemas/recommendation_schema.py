from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


ProductEventType = Literal[
    "view",
    "click",
    "add_to_cart",
    "buy",
    "review",
    "search_click",
]


class ProductEventCreate(BaseModel):
    product_id: str
    event_type: ProductEventType
    metadata: dict[str, Any] = Field(default_factory=dict)

    model_config = ConfigDict(extra="ignore")


class ProductEvent(BaseModel):
    id: str
    user_id: str
    product_id: str
    event_type: ProductEventType
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True, extra="allow")
