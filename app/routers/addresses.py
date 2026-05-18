from fastapi import APIRouter, Depends, Response, status

from app.dependencies import get_current_user
from app.schemas.address_schema import Address, AddressCreate, AddressUpdate
from app.services import address_service

router = APIRouter()


@router.get("", response_model=list[Address])
def list_addresses(current_user: dict = Depends(get_current_user)) -> list[dict]:
    return address_service.list_addresses(current_user["id"])


@router.post("", response_model=Address, status_code=status.HTTP_201_CREATED)
def add_address(
    payload: AddressCreate,
    current_user: dict = Depends(get_current_user),
) -> dict:
    return address_service.add_address(current_user["id"], payload)


@router.patch("", response_model=Address)
def update_address_compat(
    payload: AddressUpdate,
    id: str,
    current_user: dict = Depends(get_current_user),
) -> dict:
    return address_service.update_address(current_user["id"], id, payload)


@router.patch("/{address_id}", response_model=Address)
def update_address(
    address_id: str,
    payload: AddressUpdate,
    current_user: dict = Depends(get_current_user),
) -> dict:
    return address_service.update_address(current_user["id"], address_id, payload)


@router.delete("", status_code=status.HTTP_204_NO_CONTENT)
def delete_address_compat(
    id: str,
    current_user: dict = Depends(get_current_user),
) -> Response:
    address_service.delete_address(current_user["id"], id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.delete("/{address_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_address(
    address_id: str,
    current_user: dict = Depends(get_current_user),
) -> Response:
    address_service.delete_address(current_user["id"], address_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
