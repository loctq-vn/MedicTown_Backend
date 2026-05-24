from fastapi import APIRouter, Depends, status
from pydantic import BaseModel

from app.dependencies import get_current_user
from app.schemas.order_schema import Order
from app.schemas.product_schema import Product, ProductCreate, ProductUpdate
from app.schemas.shop_schema import Shop, ShopCreate, ShopUpdate
from app.services import shop_service

router = APIRouter()


class OrderStatusUpdate(BaseModel):
    status: str


@router.get("/my", response_model=list[Shop])
def list_my_shops(current_user: dict = Depends(get_current_user)) -> list[dict]:
    return shop_service.list_my_shops(current_user["id"])


@router.post("", response_model=Shop, status_code=status.HTTP_201_CREATED)
def create_shop(
    payload: ShopCreate,
    current_user: dict = Depends(get_current_user),
) -> dict:
    return shop_service.create_shop(current_user["id"], payload)


@router.get("/{shop_id}", response_model=Shop)
def get_my_shop(
    shop_id: str,
    current_user: dict = Depends(get_current_user),
) -> dict:
    return shop_service.get_my_shop(current_user["id"], shop_id)


@router.patch("/{shop_id}", response_model=Shop)
def update_shop(
    shop_id: str,
    payload: ShopUpdate,
    current_user: dict = Depends(get_current_user),
) -> dict:
    return shop_service.update_shop(current_user["id"], shop_id, payload)


@router.get("/{shop_id}/products", response_model=list[Product])
def list_shop_products(
    shop_id: str,
    current_user: dict = Depends(get_current_user),
) -> list[dict]:
    return shop_service.list_shop_products(current_user["id"], shop_id)


@router.post("/{shop_id}/products", response_model=Product, status_code=status.HTTP_201_CREATED)
def create_shop_product(
    shop_id: str,
    payload: ProductCreate,
    current_user: dict = Depends(get_current_user),
) -> dict:
    return shop_service.create_shop_product(current_user["id"], shop_id, payload)


@router.patch("/{shop_id}/products/{product_id}", response_model=Product)
def update_shop_product(
    shop_id: str,
    product_id: str,
    payload: ProductUpdate,
    current_user: dict = Depends(get_current_user),
) -> dict:
    return shop_service.update_shop_product(
        current_user["id"],
        shop_id,
        product_id,
        payload,
    )


@router.get("/{shop_id}/orders", response_model=list[Order])
def list_shop_orders(
    shop_id: str,
    current_user: dict = Depends(get_current_user),
) -> list[dict]:
    return shop_service.list_shop_orders(current_user["id"], shop_id)


@router.patch("/{shop_id}/orders/{order_id}/status", response_model=Order)
def update_shop_order_status(
    shop_id: str,
    order_id: str,
    payload: OrderStatusUpdate,
    current_user: dict = Depends(get_current_user),
) -> dict:
    return shop_service.update_shop_order_status(
        current_user["id"],
        shop_id,
        order_id,
        payload.status,
    )
