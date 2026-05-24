from fastapi import APIRouter, Depends, Header, Request

from app.dependencies import get_current_user
from app.schemas.user_schema import UserProfile, UserUpdate
from app.services import user_service

router = APIRouter()


@router.get("/me", response_model=UserProfile)
def get_me(current_user: dict = Depends(get_current_user)) -> dict:
    return user_service.get_user(current_user["id"])


@router.patch("/me", response_model=UserProfile)
def update_me(
    payload: UserUpdate,
    current_user: dict = Depends(get_current_user),
) -> dict:
    return user_service.update_user(current_user["id"], payload)


@router.post("/me/avatar")
async def upload_avatar(
    request: Request,
    filename: str | None = None,
    content_type: str | None = Header(default=None, alias="Content-Type"),
    current_user: dict = Depends(get_current_user),
) -> dict:
    content = await request.body()
    return await user_service.upload_avatar(
        current_user["id"],
        content,
        content_type=content_type,
        filename=filename,
    )
