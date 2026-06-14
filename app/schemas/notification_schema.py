from pydantic import BaseModel, ConfigDict, Field, field_validator


class DeviceTokenRequest(BaseModel):
    token: str = Field(min_length=20, max_length=4096)

    model_config = ConfigDict(extra="ignore")

    @field_validator("token", mode="before")
    @classmethod
    def normalize_token(cls, value):
        if isinstance(value, str):
            return value.strip()
        return value