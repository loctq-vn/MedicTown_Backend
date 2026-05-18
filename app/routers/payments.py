from fastapi import APIRouter, Depends

from app.dependencies import get_current_user
from app.schemas.payment_schema import Payment, PaymentCreate
from app.services import payment_service

router = APIRouter()


@router.post("", response_model=Payment)
def create_payment(
    payload: PaymentCreate,
    current_user: dict = Depends(get_current_user),
) -> dict:
    return payment_service.create_payment(current_user["id"], payload)


@router.get("/{payment_id}", response_model=Payment)
def get_payment(
    payment_id: str,
    current_user: dict = Depends(get_current_user),
) -> dict:
    return payment_service.get_payment(payment_id, current_user["id"])
