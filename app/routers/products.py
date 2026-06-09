from fastapi import APIRouter, Query

from app.schemas.product_schema import Product, ProductCategory, ProductSubcategory
from app.services import product_service

router = APIRouter()


@router.get("", response_model=list[Product])
def list_products(
    search: str | None = None,
    name: str | None = None,
    category_id: str | None = None,
    subcategory_id: str | None = None,
    shop_id: str | None = None,
    is_featured: bool | None = None,
    is_active: bool | None = None,
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> list[dict]:
    if name:
        result = product_service.list_products_by_name_filter(
            name_filter=name,
            category_id=category_id,
            subcategory_id=subcategory_id,
            shop_id=shop_id,
            is_featured=is_featured,
            is_active=is_active,
            limit=limit,
            offset=offset,
        )
    else:
        result = product_service.list_products(
            search=search,
            category_id=category_id,
            subcategory_id=subcategory_id,
            shop_id=shop_id,
            is_featured=is_featured,
            is_active=is_active,
            limit=limit,
            offset=offset,
        )
    return result["items"]


@router.get("/categories", response_model=list[ProductCategory])
def list_categories() -> list[dict]:
    return product_service.list_categories()


@router.get("/subcategories", response_model=list[ProductSubcategory])
def list_subcategories(category_id: str | None = None) -> list[dict]:
    return product_service.list_subcategories(category_id=category_id)


@router.get("/featured", response_model=list[Product])
def get_featured_products(
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> list[dict]:
    result = product_service.list_products(
        is_featured=True,
        is_active=True,
        limit=limit,
        offset=offset,
    )
    return result["items"]
