from fastapi import APIRouter, Query, status

from app.schemas.ad_schema import Advertisement
from app.services import ad_service

router = APIRouter()


@router.get("", response_model=list[Advertisement])
def list_ads(
    position: str = Query(default="home_banner"),
    limit: int = Query(default=10, ge=1, le=30),
) -> list[dict]:
    return ad_service.list_ads(position=position, limit=limit)


@router.post("/{ad_id}/view", status_code=status.HTTP_204_NO_CONTENT)
def record_ad_view(ad_id: str) -> None:
    ad_service.record_view(ad_id)


@router.post("/{ad_id}/click", status_code=status.HTTP_204_NO_CONTENT)
def record_ad_click(ad_id: str) -> None:
    ad_service.record_click(ad_id)
