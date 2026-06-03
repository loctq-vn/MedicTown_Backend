from app.services.payment_service import expire_pending_momo_payments


if __name__ == "__main__":
    expired_count = expire_pending_momo_payments()
    print(f"Expired MoMo payments: {expired_count}")
