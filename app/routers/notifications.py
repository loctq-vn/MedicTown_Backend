from typing import List
from uuid import UUID

from fastapi import APIRouter, Depends, Response, status

from app.dependencies import get_current_user
from app.schemas.notification_schema import DeviceTokenRequest, NotificationResponse
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

@router.get("", response_model=List[NotificationResponse])
def get_notifications(
    limit: int = 50,
    current_user: dict = Depends(get_current_user),
):
    return notification_service.get_notifications(
        current_user["id"],
        limit,
    )


@router.patch("/read-all", status_code=status.HTTP_204_NO_CONTENT)
def mark_all_notifications_read(
    current_user: dict = Depends(get_current_user),
) -> Response:
    notification_service.mark_all_notifications_read(current_user["id"])
    return Response(status_code=status.HTTP_204_NO_CONTENT)

@router.patch("/{notification_id}/read", status_code=status.HTTP_204_NO_CONTENT)
def mark_notification_read(
    notification_id: UUID,
    current_user: dict = Depends(get_current_user),
) -> Response:
    notification_service.mark_notification_read(
        current_user["id"],
        str(notification_id),
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)


