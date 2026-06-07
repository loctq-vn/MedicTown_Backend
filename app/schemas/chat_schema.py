from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


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
    content: str = Field(min_length=1, max_length=4000)

    model_config = ConfigDict(extra="forbid")

    @field_validator("content")
    @classmethod
    def normalize_content(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Message content cannot be blank")
        return value


class ChatMessage(BaseModel):
    id: str
    conversation_id: str
    sender_id: str
    sender_type: Literal["customer", "seller"]
    content: str
    message_type: Literal["text"] = "text"
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
