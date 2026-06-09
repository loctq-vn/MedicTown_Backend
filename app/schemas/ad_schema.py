from datetime import datetime
from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, model_validator

from app.schemas.product_schema import Product


TargetType = Literal["product", "shop", "external_url", "none"]
AdPosition = Literal["home_banner", "product_list", "popup", "checkout_banner"]
AdStatus = Literal["draft", "active", "paused", "expired"]
EditableAdStatus = Literal["draft", "active", "paused"]


class AdvertisementBase(BaseModel):
    title: str = Field(min_length=1, max_length=160)
    description: str | None = Field(default=None, max_length=2000)
    image_url: HttpUrl
    target_type: TargetType = "product"
    target_id: UUID | None = None
    target_url: HttpUrl | None = None
    position: AdPosition = "home_banner"
    priority: int = Field(default=0, ge=0)
    start_date: datetime | None = None
    end_date: datetime | None = None
    budget_amount: Decimal | None = Field(default=None, ge=0)

    @model_validator(mode="after")
    def validate_target_and_dates(self) -> "AdvertisementBase":
        if self.start_date and self.end_date and self.start_date > self.end_date:
            raise ValueError("start_date must be before or equal to end_date")
        if self.target_type in {"product", "shop"} and self.target_id is None:
            raise ValueError("target_id is required for product and shop targets")
        if self.target_type == "external_url" and self.target_url is None:
            raise ValueError("target_url is required for external_url targets")
        return self


class AdvertisementCreate(AdvertisementBase):
    status: EditableAdStatus = "draft"
    is_active: bool | None = None


class AdvertisementUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=160)
    description: str | None = Field(default=None, max_length=2000)
    image_url: HttpUrl | None = None
    target_type: TargetType | None = None
    target_id: UUID | None = None
    target_url: HttpUrl | None = None
    position: AdPosition | None = None
    priority: int | None = Field(default=None, ge=0)
    is_active: bool | None = None
    start_date: datetime | None = None
    end_date: datetime | None = None
    budget_amount: Decimal | None = Field(default=None, ge=0)
    status: EditableAdStatus | None = None


class AdvertisementStatusUpdate(BaseModel):
    status: EditableAdStatus | None = None
    is_active: bool | None = None

    @model_validator(mode="after")
    def require_status_or_active(self) -> "AdvertisementStatusUpdate":
        if self.status is None and self.is_active is None:
            raise ValueError("status or is_active is required")
        return self


class Advertisement(BaseModel):
    id: UUID
    title: str
    description: str | None = None
    image_url: str
    target_type: TargetType = "product"
    target_id: UUID | None = None
    target_url: str | None = None
    position: AdPosition = "home_banner"
    priority: int = 0
    is_active: bool = True
    start_date: datetime | None = None
    end_date: datetime | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None
    view_count: int = 0
    click_count: int = 0
    budget_amount: Decimal | None = None
    spent_amount: Decimal = Decimal("0")
    status: AdStatus = "active"
    shop_id: UUID | None = None
    created_by: UUID | None = None
    product: Product | None = None

    model_config = ConfigDict(from_attributes=True, extra="allow")
