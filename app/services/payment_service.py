from fastapi import HTTPException, status

from app.database import supabase
from app.schemas.payment_schema import PaymentCreate


def create_payment(user_id: str, payload: PaymentCreate) -> dict:
    order_response = (
        supabase.table("orders")
        .select("id,user_id,total_amount,status")
        .eq("id", payload.order_id)
        .eq("user_id", user_id)
        .maybe_single()
        .execute()
    )

    if not order_response.data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Order not found",
        )

    payment_response = (
        supabase.table("payments")
        .insert(
            {
                "order_id": payload.order_id,
                "amount": str(payload.amount),
                "method": payload.method,
                "transaction_id": payload.transaction_id,
                "payment_data": payload.payment_data,
                "status": "pending",
            }
        )
        .execute()
    )

    payment = (payment_response.data or [None])[0]
    if not payment:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unable to create payment",
        )

    return payment


def get_payment(payment_id: str, user_id: str) -> dict:
    response = (
        supabase.table("payments")
        .select("*,orders!inner(user_id)")
        .eq("id", payment_id)
        .eq("orders.user_id", user_id)
        .maybe_single()
        .execute()
    )

    if not response.data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Payment not found",
        )

    payment = response.data
    payment.pop("orders", None)
    return payment
