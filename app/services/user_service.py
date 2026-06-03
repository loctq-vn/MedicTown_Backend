from fastapi import HTTPException, status
from uuid import uuid4

from app.config import settings
from app.database import supabase
from app.schemas.user_schema import UserUpdate
from app.services.upload_validation import validate_image_upload


def get_user(user_id: str) -> dict:
    response = (
        supabase.table("users")
        .select("*")
        .eq("id", user_id)
        .maybe_single()
        .execute()
    )

    if not response.data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    return response.data


def update_user(user_id: str, payload: UserUpdate) -> dict:
    data = payload.model_dump(exclude_unset=True)
    if not data:
        return get_user(user_id)

    response = (
        supabase.table("users")
        .update(data)
        .eq("id", user_id)
        .execute()
    )

    user = (response.data or [None])[0]
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    return user


async def upload_avatar(
    user_id: str,
    content: bytes,
    content_type: str | None = None,
    filename: str | None = None,
) -> dict:
    extension, content_type = validate_image_upload(content, content_type, filename)
    file_path = f"{user_id}/upload_{uuid4().hex}.{extension}"

    try:
        supabase.storage.from_(settings.supabase_storage_bucket).upload(
            file_path,
            content,
            file_options={"content-type": content_type, "upsert": "true"},
        )
        public_url = supabase.storage.from_(settings.supabase_storage_bucket).get_public_url(
            file_path
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unable to upload avatar",
        ) from exc

    user = update_user(user_id, UserUpdate(avatar_url=public_url))
    return {
        "path": file_path,
        "url": public_url,
        "user": user,
    }
