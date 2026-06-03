from datetime import datetime
from urllib.parse import urlparse

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


def _validate_logo_url(value: str | None) -> str | None:
    value = _strip_optional(value)
    if value is None:
        return value
    parsed = urlparse(value)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError("logo_url must be a valid http or https URL")
    return value


class ShopCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    description: str | None = None
    logo_url: str | None = Field(default=None, max_length=500)
    address: str | None = Field(default=None, max_length=500)

    model_config = ConfigDict(extra="ignore")

    @field_validator("name")
    @classmethod
    def normalize_required_text(cls, value: str) -> str:
        return _strip_required(value)

    @field_validator("description", "address")
    @classmethod
    def normalize_optional_text(cls, value: str | None) -> str | None:
        return _strip_optional(value)

    @field_validator("logo_url")
    @classmethod
    def validate_logo_url(cls, value: str | None) -> str | None:
        return _validate_logo_url(value)


class ShopUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    description: str | None = None
    logo_url: str | None = Field(default=None, max_length=500)
    address: str | None = Field(default=None, max_length=500)

    model_config = ConfigDict(extra="ignore")

    @field_validator("name", "description", "address")
    @classmethod
    def normalize_text(cls, value: str | None) -> str | None:
        return _strip_optional(value)

    @field_validator("logo_url")
    @classmethod
    def validate_logo_url(cls, value: str | None) -> str | None:
        return _validate_logo_url(value)


class Shop(ShopCreate):
    id: str
    owner_id: str
    is_active: bool = True
    created_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True, extra="allow")
