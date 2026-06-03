from datetime import datetime
from urllib.parse import urlparse

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


def _is_http_url(value: str) -> bool:
    parsed = urlparse(value)
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


def _validate_image_urls(images: list[str]) -> None:
    if not images:
        raise ValueError("Product must have at least one image")
    if any(not _is_http_url(image) for image in images):
        raise ValueError("Product images must be valid http or https URLs")


class ProductBase(BaseModel):
    name: str
    brand: str | None = None
    price: float
    sale_price: float | None = None
    unit: str
    stock: int = 0
    images: list[str] = Field(default_factory=list)
    usage: str | None = None
    uses: str | None = None
    side_effects: str | None = None
    precautions: str | None = None
    storage: str | None = None
    manufacturer: str | None = None
    requires_prescription: bool = False
    is_featured: bool = False
    is_best_seller: bool = False
    is_active: bool = True
    shop_id: str | None = None
    subcategory_id: str


class ProductCreate(BaseModel):
    name: str = Field(min_length=3, max_length=120)
    brand: str | None = Field(default=None, max_length=120)
    price: float = Field(ge=0)
    sale_price: float | None = Field(default=None, ge=0)
    unit: str = Field(min_length=1, max_length=50)
    stock: int = Field(default=0, ge=0)
    images: list[str] = Field(default_factory=list)
    usage: str | None = Field(default=None, max_length=2000)
    uses: str | None = Field(default=None, max_length=2000)
    side_effects: str | None = Field(default=None, max_length=2000)
    precautions: str | None = Field(default=None, max_length=2000)
    storage: str | None = Field(default=None, max_length=2000)
    manufacturer: str | None = Field(default=None, max_length=120)
    requires_prescription: bool = False
    is_featured: bool = False
    is_best_seller: bool = False
    is_active: bool = True
    subcategory_id: str = Field(min_length=1, max_length=120)

    model_config = ConfigDict(extra="ignore")

    @model_validator(mode="after")
    def validate_product_create(self) -> "ProductCreate":
        if self.sale_price is not None and self.sale_price > self.price:
            raise ValueError("Sale price must be less than or equal to price")
        _validate_image_urls(self.images)
        return self

    @field_validator("name", "unit", "subcategory_id")
    @classmethod
    def validate_required_text(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Field cannot be blank")
        return value


class ProductUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=3, max_length=120)
    brand: str | None = Field(default=None, max_length=120)
    price: float | None = Field(default=None, ge=0)
    sale_price: float | None = Field(default=None, ge=0)
    unit: str | None = Field(default=None, min_length=1, max_length=50)
    stock: int | None = Field(default=None, ge=0)
    images: list[str] | None = None
    usage: str | None = Field(default=None, max_length=2000)
    uses: str | None = Field(default=None, max_length=2000)
    side_effects: str | None = Field(default=None, max_length=2000)
    precautions: str | None = Field(default=None, max_length=2000)
    storage: str | None = Field(default=None, max_length=2000)
    manufacturer: str | None = Field(default=None, max_length=120)
    requires_prescription: bool | None = None
    is_featured: bool | None = None
    is_best_seller: bool | None = None
    is_active: bool | None = None
    subcategory_id: str | None = Field(default=None, min_length=1, max_length=120)

    model_config = ConfigDict(extra="ignore")

    @model_validator(mode="after")
    def validate_product_update(self) -> "ProductUpdate":
        if (
            self.sale_price is not None
            and self.price is not None
            and self.sale_price > self.price
        ):
            raise ValueError("Sale price must be less than or equal to price")
        if self.images is not None:
            _validate_image_urls(self.images)
        return self

    @field_validator("name", "unit", "subcategory_id")
    @classmethod
    def validate_optional_text(cls, value: str | None) -> str | None:
        if value is None:
            return value
        value = value.strip()
        if not value:
            raise ValueError("Field cannot be blank")
        return value


class Product(ProductBase):
    id: str
    created_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True, extra="allow")


class ProductListResponse(BaseModel):
    items: list[Product]
    total: int


class ProductCategory(BaseModel):
    id: str
    name: str
    description: str | None = None
    sort_order: int = 0
    is_active: bool = True

    model_config = ConfigDict(from_attributes=True, extra="allow")


class ProductSubcategory(BaseModel):
    id: str
    category_id: str
    name: str
    description: str | None = None
    requires_prescription_default: bool = False
    sort_order: int = 0
    is_active: bool = True

    model_config = ConfigDict(from_attributes=True, extra="allow")
