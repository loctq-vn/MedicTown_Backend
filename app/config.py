import base64
import json
from functools import lru_cache

from pydantic import AliasChoices, Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "MedicTown Backend"
    app_version: str = "1.0.0"
    environment: str = "development"

    supabase_url: str = Field(..., alias="SUPABASE_URL")
    supabase_anon_key: str = Field(
        ...,
        validation_alias=AliasChoices("SUPABASE_ANON_KEY", "SUPABASE_KEY"),
    )
    supabase_storage_bucket: str = Field("avatars", alias="SUPABASE_STORAGE_BUCKET")

    cors_origins_raw: str = Field("*", alias="CORS_ORIGINS")

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    @model_validator(mode="after")
    def reject_service_role_key(self) -> "Settings":
        if _jwt_role(self.supabase_anon_key) == "service_role":
            raise ValueError(
                "SUPABASE_ANON_KEY must be the Supabase anon public key, not the service role key"
            )
        return self

    @property
    def cors_origins(self) -> list[str]:
        if self.cors_origins_raw.strip() == "*":
            return ["*"]
        return [
            origin.strip()
            for origin in self.cors_origins_raw.split(",")
            if origin.strip()
        ]


def _jwt_role(token: str) -> str | None:
    parts = token.split(".")
    if len(parts) < 2:
        return None

    payload = parts[1]
    padding = "=" * (-len(payload) % 4)
    try:
        decoded = base64.urlsafe_b64decode(payload + padding)
        data = json.loads(decoded)
    except (ValueError, json.JSONDecodeError):
        return None
    return data.get("role")


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
