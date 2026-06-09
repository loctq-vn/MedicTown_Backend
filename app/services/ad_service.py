from datetime import datetime, timezone
from uuid import uuid4

from fastapi import HTTPException, status

from app.config import settings
from app.database import supabase
from app.schemas.ad_schema import (
    AdvertisementCreate,
    AdvertisementStatusUpdate,
    AdvertisementUpdate,
)
from app.services.shop_service import get_my_shop
from app.services.upload_validation import validate_image_upload


def list_ads(position: str = "home_banner", limit: int = 10) -> list[dict]:
    response = (
        supabase.table("advertisements")
        .select("*")
        .eq("is_active", True)
        .eq("status", "active")
        .eq("position", position)
        .order("priority", desc=True)
        .order("created_at", desc=True)
        .limit(limit)
        .execute()
    )

    ads = [ad for ad in response.data or [] if _is_in_active_date_range(ad)]
    _attach_target_products(ads)
    return [
        ad
        for ad in ads
        if ad.get("target_type") != "product" or ad.get("product") is not None
    ]


def list_shop_ads(
    user_id: str,
    shop_id: str,
    search: str | None = None,
    ad_status: str | None = None,
    position: str | None = None,
    limit: int = 50,
    offset: int = 0,
    fetch_all: bool = False,
) -> list[dict]:
    get_my_shop(user_id, shop_id)
    query = (
        supabase.table("advertisements")
        .select("*")
        .eq("shop_id", shop_id)
    )
    if search:
        escaped = search.replace(",", " ").strip()
        if escaped:
            query = query.or_(
                f"title.ilike.%{escaped}%,description.ilike.%{escaped}%"
            )
    if position:
        query = query.eq("position", position)

    query = query.order("created_at", desc=True)
    if fetch_all:
        ads = []
        page_size = 1000
        page_offset = 0
        while True:
            response = query.range(
                page_offset,
                page_offset + page_size - 1,
            ).execute()
            page = response.data or []
            ads.extend(page)
            if len(page) < page_size:
                break
            page_offset += page_size
    else:
        response = query.range(offset, offset + limit - 1).execute()
        ads = response.data or []
    _expire_ads(ads)
    if ad_status:
        ads = [ad for ad in ads if ad.get("status") == ad_status]
    return ads


def get_shop_ad(user_id: str, shop_id: str, ad_id: str) -> dict:
    get_my_shop(user_id, shop_id)
    response = (
        supabase.table("advertisements")
        .select("*")
        .eq("id", ad_id)
        .eq("shop_id", shop_id)
        .maybe_single()
        .execute()
    )
    if not response.data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Advertisement not found",
        )
    ad = response.data
    _expire_ads([ad])
    return ad


def create_shop_ad(
    user_id: str,
    shop_id: str,
    payload: AdvertisementCreate,
) -> dict:
    get_my_shop(user_id, shop_id)
    data = payload.model_dump(exclude_unset=True, mode="json")
    data["shop_id"] = shop_id
    data["created_by"] = user_id
    _normalize_target(data)
    _validate_target(user_id, shop_id, data)
    _normalize_lifecycle(data, default_status="draft")

    response = supabase.table("advertisements").insert(data).execute()
    ad = (response.data or [None])[0]
    if not ad:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unable to create advertisement",
        )
    return ad


def update_shop_ad(
    user_id: str,
    shop_id: str,
    ad_id: str,
    payload: AdvertisementUpdate,
) -> dict:
    current = get_shop_ad(user_id, shop_id, ad_id)
    data = payload.model_dump(exclude_unset=True, mode="json")
    if not data:
        return current

    merged = {**current, **data}
    _normalize_target(merged)
    _validate_target(user_id, shop_id, merged)
    _validate_dates(merged)
    if any(key in data for key in ("target_type", "target_id", "target_url")):
        data["target_id"] = merged.get("target_id")
        data["target_url"] = merged.get("target_url")
    _normalize_lifecycle(data, current=current)

    response = (
        supabase.table("advertisements")
        .update(data)
        .eq("id", ad_id)
        .eq("shop_id", shop_id)
        .execute()
    )
    ad = (response.data or [None])[0]
    if not ad:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Advertisement not found",
        )
    return ad


def update_shop_ad_status(
    user_id: str,
    shop_id: str,
    ad_id: str,
    payload: AdvertisementStatusUpdate,
) -> dict:
    current = get_shop_ad(user_id, shop_id, ad_id)
    data = payload.model_dump(exclude_unset=True)
    _normalize_lifecycle(data, current=current)
    response = (
        supabase.table("advertisements")
        .update(data)
        .eq("id", ad_id)
        .eq("shop_id", shop_id)
        .execute()
    )
    ad = (response.data or [None])[0]
    if not ad:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Advertisement not found",
        )
    return ad


def delete_shop_ad(user_id: str, shop_id: str, ad_id: str) -> None:
    get_shop_ad(user_id, shop_id, ad_id)
    (
        supabase.table("advertisements")
        .delete()
        .eq("id", ad_id)
        .eq("shop_id", shop_id)
        .execute()
    )


async def upload_ad_image(
    user_id: str,
    shop_id: str,
    content: bytes,
    content_type: str | None = None,
    filename: str | None = None,
) -> dict:
    get_my_shop(user_id, shop_id)
    extension, content_type = validate_image_upload(content, content_type, filename)
    file_path = f"shops/{shop_id}/advertisements/upload_{uuid4().hex}.{extension}"

    try:
        supabase.storage.from_(settings.supabase_storage_bucket).upload(
            file_path,
            content,
            file_options={"content-type": content_type, "upsert": "true"},
        )
        public_url = supabase.storage.from_(
            settings.supabase_storage_bucket
        ).get_public_url(file_path)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unable to upload advertisement image",
        ) from exc

    return {"path": file_path, "url": public_url}


def record_view(ad_id: str) -> None:
    supabase.rpc("increment_advertisement_view", {"p_ad_id": ad_id}).execute()


def record_click(ad_id: str) -> None:
    supabase.rpc("increment_advertisement_click", {"p_ad_id": ad_id}).execute()


def _normalize_lifecycle(
    data: dict,
    current: dict | None = None,
    default_status: str = "active",
) -> None:
    requested_status = data.get("status")
    requested_active = data.get("is_active")

    if requested_status is not None:
        data["is_active"] = requested_status == "active"
    elif requested_active is not None:
        data["status"] = "active" if requested_active else "paused"
    else:
        current_status = (current or {}).get("status", default_status)
        data["status"] = current_status
        data["is_active"] = current_status == "active"

    if "end_date" in data:
        end_date = _parse_datetime(data.get("end_date"))
    else:
        end_date = _parse_datetime((current or {}).get("end_date"))
    if end_date is not None and end_date < datetime.now(timezone.utc):
        data["status"] = "expired"
        data["is_active"] = False


def _normalize_target(data: dict) -> None:
    target_type = data.get("target_type")
    if target_type == "external_url":
        data["target_id"] = None
    elif target_type == "none":
        data["target_id"] = None
        data["target_url"] = None
    else:
        data["target_url"] = None


def _validate_target(user_id: str, shop_id: str, data: dict) -> None:
    target_type = data.get("target_type")
    target_id = data.get("target_id")
    target_url = data.get("target_url")

    if target_type == "product":
        if not target_id:
            _bad_request("target_id is required for product targets")
        response = (
            supabase.table("products")
            .select("id")
            .eq("id", str(target_id))
            .eq("shop_id", shop_id)
            .maybe_single()
            .execute()
        )
        if not response.data:
            _bad_request("Target product must belong to the selected shop")
    elif target_type == "shop":
        if str(target_id or "") != str(shop_id):
            _bad_request("Target shop must be the selected shop")
        get_my_shop(user_id, shop_id)
    elif target_type == "external_url":
        if not target_url or not str(target_url).lower().startswith("https://"):
            _bad_request("External target_url must use HTTPS")

    _validate_dates(data)


def _validate_dates(data: dict) -> None:
    start_date = _parse_datetime(data.get("start_date"))
    end_date = _parse_datetime(data.get("end_date"))
    if start_date and end_date and start_date > end_date:
        _bad_request("start_date must be before or equal to end_date")


def _bad_request(detail: str) -> None:
    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=detail)


def _expire_ads(ads: list[dict]) -> None:
    for ad in ads:
        if ad.get("status") == "expired":
            continue
        end_date = _parse_datetime(ad.get("end_date"))
        if end_date is None or end_date >= datetime.now(timezone.utc):
            continue
        ad["status"] = "expired"
        ad["is_active"] = False
        (
            supabase.table("advertisements")
            .update({"status": "expired", "is_active": False})
            .eq("id", ad["id"])
            .execute()
        )


def _is_in_active_date_range(ad: dict) -> bool:
    now = datetime.now(timezone.utc)
    start_date = _parse_datetime(ad.get("start_date"))
    end_date = _parse_datetime(ad.get("end_date"))
    return not (
        (start_date is not None and start_date > now)
        or (end_date is not None and end_date < now)
    )


def _parse_datetime(value: str | datetime | None) -> datetime | None:
    if not value:
        return None
    if isinstance(value, datetime):
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value
    normalized = value.replace("Z", "+00:00")
    parsed = datetime.fromisoformat(normalized)
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed


def _attach_target_products(ads: list[dict]) -> None:
    product_ids = [
        ad["target_id"]
        for ad in ads
        if ad.get("target_type") == "product" and ad.get("target_id")
    ]
    if not product_ids:
        return

    response = (
        supabase.table("products")
        .select("*")
        .in_("id", product_ids)
        .eq("is_active", True)
        .execute()
    )
    products_by_id = {product["id"]: product for product in response.data or []}

    for ad in ads:
        if ad.get("target_type") == "product":
            ad["product"] = products_by_id.get(ad.get("target_id"))
