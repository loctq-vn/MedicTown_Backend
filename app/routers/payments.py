from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse

from app.services import payment_service

router = APIRouter()


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
