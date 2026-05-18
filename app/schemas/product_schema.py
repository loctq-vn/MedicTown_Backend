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


class Product(ProductBase):
    id: str
    created_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True, extra="allow")


class ProductListResponse(BaseModel):
    items: list[Product]
    total: int
