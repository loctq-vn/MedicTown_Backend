from fastapi import APIRouter, Depends, Response, status

from app.dependencies import get_current_user
from app.schemas.notification_schema import DeviceTokenRequest
from app.services import notification_service


router = APIRouter()


@router.put(
    "/device-token",
    status_code=status.HTTP_204_NO_CONTENT,
)
def register_device_token(
    payload: DeviceTokenRequest,
    current_user: dict = Depends(get_current_user),
) -> Response:
    notification_service.register_device_token(
        current_user["id"],
        payload,
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.delete(
    "/device-token",
    status_code=status.HTTP_204_NO_CONTENT,
)
def unregister_device_token(
    payload: DeviceTokenRequest,
    current_user: dict = Depends(get_current_user),
) -> Response:
    notification_service.unregister_device_token(
        current_user["id"],
        payload,
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)