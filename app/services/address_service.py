from fastapi import HTTPException, status

from app.database import supabase
from app.schemas.address_schema import AddressCreate, AddressUpdate
from app.utils.postgrest_filters import parse_eq_filter


def list_addresses(user_id: str) -> list[dict]:
    response = (
        supabase.table("address")
        .select("*")
        .eq("user_id", user_id)
        .order("created_at", desc=True)
        .execute()
    )
    return response.data or []


def add_address(user_id: str, payload: AddressCreate) -> dict:
    data = payload.model_dump(exclude_unset=True)
    data["user_id"] = user_id

    response = supabase.table("address").insert(data).execute()
    address = (response.data or [None])[0]
    if not address:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unable to add address",
        )
    return address


def update_address(user_id: str, address_id: str, payload: AddressUpdate) -> dict:
    address_id = parse_eq_filter(address_id) or address_id
    data = payload.model_dump(exclude_unset=True)
    response = (
        supabase.table("address")
        .update(data)
        .eq("id", address_id)
        .eq("user_id", user_id)
        .execute()
    )

    address = (response.data or [None])[0]
    if not address:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Address not found",
        )
    return address


def delete_address(user_id: str, address_id: str) -> None:
    address_id = parse_eq_filter(address_id) or address_id
    response = (
        supabase.table("address")
        .delete()
        .eq("id", address_id)
        .eq("user_id", user_id)
        .execute()
    )
    if not response.data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Address not found",
        )
