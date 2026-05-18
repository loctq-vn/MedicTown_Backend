from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.user_schema import UserProfile


class ReviewCreate(BaseModel):
    product_id: str
    order_item_id: str | None = None
    rating: int = Field(ge=1, le=5)
    comment: str | None = None
    images: list[str] = Field(default_factory=list)

    model_config = ConfigDict(extra="ignore")


class Review(BaseModel):
    id: str
    product_id: str
    order_item_id: str | None = None
    user_id: str
    rating: int
    comment: str | None = None
    images: list[str] = Field(default_factory=list)
    users: UserProfile | None = None

    model_config = ConfigDict(from_attributes=True, extra="allow")
