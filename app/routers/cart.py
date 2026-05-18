from fastapi import APIRouter, Depends, Response, status

from app.dependencies import get_current_user
from app.schemas.cart_schema import CartItem, CartItemCreate, CartItemUpdate
from app.services import cart_service

router = APIRouter()


@router.get("", response_model=list[CartItem])
def list_cart_items(
    product_id: str | None = None,
    user_id: str | None = None,
    current_user: dict = Depends(get_current_user),
) -> list[dict]:
    return cart_service.list_cart_items(current_user["id"], product_id)


@router.post("", response_model=CartItem, status_code=status.HTTP_201_CREATED)
def add_to_cart(
    payload: CartItemCreate,
    current_user: dict = Depends(get_current_user),
) -> dict:
    return cart_service.add_to_cart(current_user["id"], payload)


@router.patch("", response_model=CartItem)
def update_cart_item_compat(
    payload: CartItemUpdate,
    id: str,
    current_user: dict = Depends(get_current_user),
) -> dict:
    return cart_service.update_cart_item(current_user["id"], id, payload)


@router.patch("/{cart_item_id}", response_model=CartItem)
def update_cart_item(
    cart_item_id: str,
    payload: CartItemUpdate,
    current_user: dict = Depends(get_current_user),
) -> dict:
    return cart_service.update_cart_item(current_user["id"], cart_item_id, payload)


@router.delete("/{cart_item_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_cart_item(
    cart_item_id: str,
    current_user: dict = Depends(get_current_user),
) -> Response:
    cart_service.delete_cart_item(current_user["id"], cart_item_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.delete("", status_code=status.HTTP_204_NO_CONTENT)
def delete_cart_items(
    id: str | None = None,
    ids: str | None = None,
    user_id: str | None = None,
    current_user: dict = Depends(get_current_user),
) -> Response:
    cart_service.delete_cart_items_from_filter(current_user["id"], ids or id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
