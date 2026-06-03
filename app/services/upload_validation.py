from pathlib import Path

from fastapi import HTTPException, status

from app.config import settings


ALLOWED_IMAGE_TYPES = {
    "jpg": "image/jpeg",
    "jpeg": "image/jpeg",
    "png": "image/png",
    "webp": "image/webp",
}


def validate_image_upload(
    content: bytes,
    content_type: str | None = None,
    filename: str | None = None,
) -> tuple[str, str]:
    if not content:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Empty file",
        )
    if len(content) > settings.upload_max_bytes:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="File exceeds max upload size",
        )

    extension = _extension_from_filename(filename)
    if extension not in ALLOWED_IMAGE_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Unsupported file extension",
        )

    detected_type = _detect_image_mime(content)
    expected_type = ALLOWED_IMAGE_TYPES[extension]
    declared_type = (content_type or "").split(";", 1)[0].strip().lower()
    if detected_type != expected_type:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File content does not match extension",
        )
    if declared_type and declared_type != detected_type:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File content does not match MIME type",
        )

    return extension, detected_type


def _extension_from_filename(filename: str | None) -> str:
    if not filename:
        return "jpg"
    return Path(filename).suffix.lower().lstrip(".")


def _detect_image_mime(content: bytes) -> str | None:
    if content.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if content.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if content.startswith(b"RIFF") and len(content) >= 12 and content[8:12] == b"WEBP":
        return "image/webp"
    return None
