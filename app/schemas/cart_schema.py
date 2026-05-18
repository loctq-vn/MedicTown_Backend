from pydantic import BaseModel, ConfigDict, Field

from app.schemas.product_schema import Product


class CartItemCreate(BaseModel):
    product_id: str
    quantity: int = Field(gt=0)

    model_config = ConfigDict(extra="ignore")


class CartItemUpdate(BaseModel):
    quantity: int = Field(gt=0)

    model_config = ConfigDict(extra="ignore")


class CartItem(BaseModel):
    id: str
    user_id: str
    product_id: str
    quantity: int
    products: Product | None = None
    isSelected: bool = False

    model_config = ConfigDict(from_attributes=True, extra="allow")
