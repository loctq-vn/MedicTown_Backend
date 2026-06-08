from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator


class ChatConversation(BaseModel):
    id: str
    shop_id: str
    customer_id: str
    last_message_at: datetime | None = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True, extra="allow")


class ChatMessageCreate(BaseModel):
    conversation_id: UUID
    client_message_id: UUID
    content: str | None = Field(default=None, max_length=4000)
    message_type: Literal["text", "image", "order", "product"] = "text"
    metadata: dict[str, Any] = Field(default_factory=dict)

    model_config = ConfigDict(extra="forbid")

    @model_validator(mode="after")
    def validate_message_payload(self) -> "ChatMessageCreate":
        if self.content is not None:
            self.content = self.content.strip()

        if self.message_type == "text":
            if not self.content:
                raise ValueError("Message content cannot be blank")
            return self

        if self.message_type == "image":
            url = str(self.metadata.get("url") or "").strip()
            if not url:
                raise ValueError("Image message requires metadata.url")
            return self

        if self.message_type == "order":
            order_id = str(self.metadata.get("order_id") or "").strip()
            if not order_id:
                raise ValueError("Order message requires metadata.order_id")
            return self

        if self.message_type == "product":
            product_id = str(self.metadata.get("product_id") or "").strip()
            if not product_id:
                raise ValueError("Product message requires metadata.product_id")
            return self

        return self


class ChatMessage(BaseModel):
    id: str
    conversation_id: str
    sender_id: str
    sender_type: Literal["customer", "seller"]
    content: str | None = None
    message_type: Literal["text", "image", "order", "product"] = "text"
    metadata: dict[str, Any] = Field(default_factory=dict)
    client_message_id: str
    read_at: datetime | None = None
    created_at: datetime
    deleted_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True, extra="allow")


class ChatMessagePage(BaseModel):
    items: list[ChatMessage] = Field(default_factory=list)
    next_cursor: datetime | None = None
    next_cursor_id: str | None = None


class ChatReadRequest(BaseModel):
    conversation_id: UUID

    model_config = ConfigDict(extra="forbid")


class ChatReadResult(BaseModel):
    updated_count: int
    read_at: datetime


class ChatCustomerSummary(BaseModel):
    id: str
    name: str
    avatar_url: str | None = None

    model_config = ConfigDict(from_attributes=True, extra="allow")


class SellerConversationItem(BaseModel):
    conversation: ChatConversation
    customer: ChatCustomerSummary
    last_message: ChatMessage | None = None
    unread_count: int = 0
