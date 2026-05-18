from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr


class UserUpdate(BaseModel):
    name: str | None = None
    phone: str | None = None
    avatar_url: str | None = None

    model_config = ConfigDict(extra="ignore")


class UserProfile(UserUpdate):
    id: str
    email: EmailStr | None = None
    role: str | None = None
    created_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True, extra="allow")
