from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field


class ProductBase(BaseModel):
    name: str = ""
    brand: str | None = None
    price: float = 0
    sale_price: float | None = None
    stock: int = 0
    images: list[str] = Field(default_factory=list)
    description: str | None = None
    usage: str | None = None
    indications: str | None = None
    contraindications: str | None = None
    manufacturer: str | None = None
    requires_prescription: bool = False
    is_featured: bool = False
    is_best_seller: bool = False
    is_active: bool = True
    shop_id: str | None = None


class ProductCreate(BaseModel):
    name: str = Field(min_length=1)
    brand: str | None = None
    price: float = Field(ge=0)
    sale_price: float | None = Field(default=None, ge=0)
    stock: int = Field(default=0, ge=0)
    images: list[str] = Field(default_factory=list)
    description: str | None = None
    usage: str | None = None
    indications: str | None = None
    contraindications: str | None = None
    manufacturer: str | None = None
    requires_prescription: bool = False
    is_featured: bool = False
    is_best_seller: bool = False
    is_active: bool = True

    model_config = ConfigDict(extra="ignore")


class ProductUpdate(BaseModel):
    name: str | None = None
    brand: str | None = None
    price: float | None = Field(default=None, ge=0)
    sale_price: float | None = Field(default=None, ge=0)
    stock: int | None = Field(default=None, ge=0)
    images: list[str] | None = None
    description: str | None = None
    usage: str | None = None
    indications: str | None = None
    contraindications: str | None = None
    manufacturer: str | None = None
    requires_prescription: bool | None = None
    is_featured: bool | None = None
    is_best_seller: bool | None = None
    is_active: bool | None = None

    model_config = ConfigDict(extra="ignore")


class Product(ProductBase):
    id: str
    created_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True, extra="allow")


class ProductListResponse(BaseModel):
    items: list[Product]
    total: int
