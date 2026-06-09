from fastapi import APIRouter, Depends, Header, Query, Request, status
from pydantic import BaseModel

from app.dependencies import get_current_user
from app.schemas.order_schema import Order
from app.schemas.ad_schema import (
    Advertisement,
    AdvertisementCreate,
    AdvertisementStatusUpdate,
    AdvertisementUpdate,
)
from app.schemas.product_schema import Product, ProductCreate, ProductUpdate
from app.schemas.shop_schema import Shop, ShopCreate, ShopUpdate
from app.services import ad_service, shop_service

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


@router.get("/{shop_id}/ads", response_model=list[Advertisement])
def list_shop_ads(
    shop_id: str,
    search: str | None = Query(default=None),
    ad_status: str | None = Query(default=None, alias="status"),
    position: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    fetch_all: bool = Query(default=False),
    current_user: dict = Depends(get_current_user),
) -> list[dict]:
    return ad_service.list_shop_ads(
        current_user["id"],
        shop_id,
        search=search,
        ad_status=ad_status,
        position=position,
        limit=limit,
        offset=offset,
        fetch_all=fetch_all,
    )


@router.post(
    "/{shop_id}/ads",
    response_model=Advertisement,
    status_code=status.HTTP_201_CREATED,
)
def create_shop_ad(
    shop_id: str,
    payload: AdvertisementCreate,
    current_user: dict = Depends(get_current_user),
) -> dict:
    return ad_service.create_shop_ad(current_user["id"], shop_id, payload)


@router.get("/{shop_id}/ads/{ad_id}", response_model=Advertisement)
def get_shop_ad(
    shop_id: str,
    ad_id: str,
    current_user: dict = Depends(get_current_user),
) -> dict:
    return ad_service.get_shop_ad(current_user["id"], shop_id, ad_id)


@router.patch("/{shop_id}/ads/{ad_id}", response_model=Advertisement)
def update_shop_ad(
    shop_id: str,
    ad_id: str,
    payload: AdvertisementUpdate,
    current_user: dict = Depends(get_current_user),
) -> dict:
    return ad_service.update_shop_ad(
        current_user["id"],
        shop_id,
        ad_id,
        payload,
    )


@router.patch("/{shop_id}/ads/{ad_id}/status", response_model=Advertisement)
def update_shop_ad_status(
    shop_id: str,
    ad_id: str,
    payload: AdvertisementStatusUpdate,
    current_user: dict = Depends(get_current_user),
) -> dict:
    return ad_service.update_shop_ad_status(
        current_user["id"],
        shop_id,
        ad_id,
        payload,
    )


@router.delete(
    "/{shop_id}/ads/{ad_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_shop_ad(
    shop_id: str,
    ad_id: str,
    current_user: dict = Depends(get_current_user),
) -> None:
    ad_service.delete_shop_ad(current_user["id"], shop_id, ad_id)


@router.post("/{shop_id}/ads/images")
async def upload_shop_ad_image(
    shop_id: str,
    request: Request,
    filename: str | None = None,
    content_type: str | None = Header(default=None, alias="Content-Type"),
    current_user: dict = Depends(get_current_user),
) -> dict:
    content = await request.body()
    return await ad_service.upload_ad_image(
        current_user["id"],
        shop_id,
        content,
        content_type=content_type,
        filename=filename,
    )


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


@router.post("/{shop_id}/products/images")
async def upload_shop_product_image(
    shop_id: str,
    request: Request,
    filename: str | None = None,
    content_type: str | None = Header(default=None, alias="Content-Type"),
    current_user: dict = Depends(get_current_user),
) -> dict:
    content = await request.body()
    return await shop_service.upload_product_image(
        current_user["id"],
        shop_id,
        content,
        content_type=content_type,
        filename=filename,
    )


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
