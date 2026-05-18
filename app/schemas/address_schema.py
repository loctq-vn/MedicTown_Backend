from datetime import datetime

from pydantic import BaseModel, ConfigDict


class AddressCreate(BaseModel):
    recipient_name: str | None = None
    location: str | None = None
    location_name: str | None = None
    phone_number: str | None = None

    model_config = ConfigDict(extra="ignore")


class AddressUpdate(BaseModel):
    recipient_name: str | None = None
    location: str | None = None
    location_name: str | None = None
    phone_number: str | None = None

    model_config = ConfigDict(extra="ignore")


class Address(AddressCreate):
    id: str
    user_id: str
    created_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True, extra="allow")
