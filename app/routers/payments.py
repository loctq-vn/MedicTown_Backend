from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse

from app.dependencies import get_current_user
from app.schemas.order_schema import OrderCreate, Payment
from app.services import payment_service

router = APIRouter()


@router.post("/momo/checkout", response_model=Payment)
def create_momo_checkout(
    payload: OrderCreate,
    current_user: dict = Depends(get_current_user),
) -> dict:
    return payment_service.create_momo_checkout(current_user["id"], payload)


@router.post("/momo/ipn")
async def momo_ipn(request: Request) -> dict:
    payload = await request.json()
    return payment_service.handle_momo_ipn(payload)


@router.get("/momo/redirect", response_class=HTMLResponse)
def momo_redirect() -> str:
    return """
    <html>
      <body>
        <p>Thanh toán MoMo đã được xử lý. Bạn có thể quay lại ứng dụng MedicTown.</p>
      </body>
    </html>
    """
