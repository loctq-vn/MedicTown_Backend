from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator


def _strip_optional(value: str | None) -> str | None:
    if value is None:
        return value
    value = value.strip()
    return value or None


def _strip_required(value: str) -> str:
    value = value.strip()
    if not value:
        raise ValueError("Field cannot be blank")
    return value


class AddressCreate(BaseModel):
    recipient_name: str = Field(min_length=1, max_length=120)
    location: str = Field(min_length=1, max_length=500)
    location_name: str | None = Field(default=None, max_length=255)
    phone_number: str = Field(min_length=8, max_length=20)

    model_config = ConfigDict(extra="ignore")

    @field_validator("recipient_name", "location", "phone_number")
    @classmethod
    def normalize_required_text(cls, value: str) -> str:
        return _strip_required(value)

    @field_validator("location_name")
    @classmethod
    def normalize_optional_text(cls, value: str | None) -> str | None:
        return _strip_optional(value)


class AddressUpdate(BaseModel):
    recipient_name: str | None = Field(default=None, min_length=1, max_length=120)
    location: str | None = Field(default=None, min_length=1, max_length=500)
    location_name: str | None = Field(default=None, max_length=255)
    phone_number: str | None = Field(default=None, min_length=8, max_length=20)

    model_config = ConfigDict(extra="ignore")

    @field_validator("recipient_name", "location", "location_name", "phone_number")
    @classmethod
    def normalize_text(cls, value: str | None) -> str | None:
        return _strip_optional(value)


class Address(AddressCreate):
    id: str
    user_id: str
    created_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True, extra="allow")
