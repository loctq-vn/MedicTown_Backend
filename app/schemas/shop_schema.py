from datetime import datetime

from pydantic import BaseModel, ConfigDict


class ShopCreate(BaseModel):
    name: str
    description: str | None = None
    logo_url: str | None = None
    address: str | None = None

    model_config = ConfigDict(extra="ignore")


class ShopUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    logo_url: str | None = None
    address: str | None = None

    model_config = ConfigDict(extra="ignore")


class Shop(ShopCreate):
    id: str
    owner_id: str
    is_active: bool = True
    created_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True, extra="allow")
