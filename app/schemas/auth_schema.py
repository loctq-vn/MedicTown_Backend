from typing import Any

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=6)
    data: dict[str, Any] | None = None
    name: str | None = None
    full_name: str | None = None
    phone: str | None = None

    model_config = ConfigDict(extra="allow")


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class GoogleLoginRequest(BaseModel):
    provider: str = "google"
    id_token: str
    nonce: str | None = None


class UserResponse(BaseModel):
    id: str
    email: EmailStr | None = None
    name: str | None = None
    phone: str | None = None
    role: str | None = None
    user_metadata: dict[str, Any] = Field(default_factory=dict)


class AuthResponse(BaseModel):
    access_token: str | None = None
    refresh_token: str | None = None
    token_type: str = "bearer"
    user: UserResponse
