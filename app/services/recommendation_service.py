from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from fastapi import HTTPException, status

from app.database import get_service_supabase_client, supabase
from app.schemas.recommendation_schema import ProductEventCreate

PRODUCT_SELECT = (
    "id,name,brand,price,sale_price,unit,stock,images,usage,uses,side_effects,"
    "precautions,storage,manufacturer,requires_prescription,is_featured,"
    "is_best_seller,is_active,shop_id,subcategory_id,created_at"
)
MAX_CANDIDATE_PRODUCTS = 500
MAX_USER_EVENTS = 200
MAX_USER_ORDERS = 100
RECENT_PURCHASE_EXCLUSION_DAYS = 30


@dataclass
class RecommendationContext:
    purchase_products: list[dict]
    add_to_cart_products: list[dict]
    view_products: list[dict]

    @property
    def all_products(self) -> list[dict]:
        products_by_id: dict[str, dict] = {}
        for product in (
            self.purchase_products
            + self.add_to_cart_products
            + self.view_products
        ):
            if product.get("id"):
                products_by_id[product["id"]] = product
        return list(products_by_id.values())


def create_product_event(user_id: str, payload: ProductEventCreate) -> dict:
    _ensure_product_exists(payload.product_id)

    response = (
        supabase.table("product_events")
        .insert(
            {
                "user_id": user_id,
                "product_id": payload.product_id,
                "event_type": payload.event_type,
                "metadata": payload.metadata or {},
            }
        )
        .execute()
    )
    event = (response.data or [None])[0]
    if not event:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unable to record product event",
        )
    return event


def _ensure_product_exists(product_id: str) -> None:
    response = (
        supabase.table("products")
        .select("id")
        .eq("id", product_id)
        .maybe_single()
        .execute()
    )
    if not response.data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Product not found",
        )


def list_user_recommendations(user_id: str, limit: int = 20) -> list[dict]:
    user_signals = _load_user_signals(user_id)
    signal_product_ids = _unique_preserve_order(
        user_signals["purchase_ids"]
        + user_signals["add_to_cart_ids"]
        + user_signals["view_ids"]
    )
    product_by_id = _load_products_by_ids(signal_product_ids)
    context = RecommendationContext(
        purchase_products=[
            product_by_id[product_id]
            for product_id in user_signals["purchase_ids"]
            if product_id in product_by_id
        ],
        add_to_cart_products=[
            product_by_id[product_id]
            for product_id in user_signals["add_to_cart_ids"]
            if product_id in product_by_id
        ],
        view_products=[
            product_by_id[product_id]
            for product_id in user_signals["view_ids"]
            if product_id in product_by_id
        ],
    )
    return _rank_candidate_products(
        context=context,
        exclude_product_ids=set(user_signals["recent_purchase_ids"]),
        limit=limit,
    )


def list_related_products(product_id: str, limit: int = 10) -> list[dict]:
    product = _load_active_product(product_id)
    context = RecommendationContext(
        purchase_products=[],
        add_to_cart_products=[],
        view_products=[product],
    )
    return _rank_candidate_products(
        context=context,
        exclude_product_ids={product_id},
        limit=limit,
    )


def _rank_candidate_products(
    context: RecommendationContext,
    exclude_product_ids: set[str],
    limit: int,
) -> list[dict]:
    candidates = _load_candidate_products()
    best_seller_scores = _load_best_seller_scores()
    rating_scores = _load_rating_scores()
    return _rank_products(
        candidates=candidates,
        context=context,
        best_seller_scores=best_seller_scores,
        rating_scores=rating_scores,
        exclude_product_ids=exclude_product_ids,
        limit=limit,
    )


def _rank_products(
    candidates: list[dict],
    context: RecommendationContext,
    best_seller_scores: dict[str, float],
    rating_scores: dict[str, float],
    exclude_product_ids: set[str],
    limit: int,
) -> list[dict]:
    anchor_products = context.all_products
    anchor_subcategories = {
        product.get("subcategory_id")
        for product in anchor_products
        if product.get("subcategory_id")
    }
    anchor_shops = {
        product.get("shop_id")
        for product in anchor_products
        if product.get("shop_id")
    }
    anchor_brands = {
        _normalize_text(product.get("brand"))
        for product in anchor_products
        if _normalize_text(product.get("brand"))
    }
    anchor_manufacturers = {
        _normalize_text(product.get("manufacturer"))
        for product in anchor_products
        if _normalize_text(product.get("manufacturer"))
    }

    ranked: list[dict] = []
    for candidate in candidates:
        product_id = candidate.get("id")
        if not product_id or product_id in exclude_product_ids:
            continue

        if candidate.get("is_active") is False or int(candidate.get("stock") or 0) <= 0:
            continue

        purchase_match = _has_affinity(candidate, context.purchase_products)
        add_to_cart_match = _has_affinity(candidate, context.add_to_cart_products)
        view_match = _has_affinity(candidate, context.view_products)
        same_subcategory = candidate.get("subcategory_id") in anchor_subcategories
        same_brand = (
            candidate.get("shop_id") in anchor_shops
            or _normalize_text(candidate.get("brand")) in anchor_brands
            or _normalize_text(candidate.get("manufacturer")) in anchor_manufacturers
        )
        best_seller_score = max(
            best_seller_scores.get(product_id, 0),
            1 if candidate.get("is_best_seller") else 0,
        )
        avg_rating_score = rating_scores.get(product_id, 0)

        score = (
            5 * int(purchase_match)
            + 3 * int(add_to_cart_match)
            + 2 * int(view_match)
            + 2 * int(same_subcategory)
            + 1 * int(same_brand)
            + 1.5 * best_seller_score
            + 1 * avg_rating_score
        )

        recommendation = dict(candidate)
        recommendation["recommendation_score"] = round(score, 4)
        recommendation["recommendation_reasons"] = _build_reasons(
            purchase_match=purchase_match,
            add_to_cart_match=add_to_cart_match,
            view_match=view_match,
            same_subcategory=same_subcategory,
            same_brand=same_brand,
            best_seller_score=best_seller_score,
            avg_rating_score=avg_rating_score,
        )
        ranked.append(recommendation)

    ranked.sort(
        key=lambda product: (
            product.get("recommendation_score", 0),
            product.get("created_at") or "",
        ),
        reverse=True,
    )
    return ranked[:limit]


def _build_reasons(
    purchase_match: bool,
    add_to_cart_match: bool,
    view_match: bool,
    same_subcategory: bool,
    same_brand: bool,
    best_seller_score: float,
    avg_rating_score: float,
) -> list[str]:
    reasons: list[str] = []
    if purchase_match:
        reasons.append("purchase_match")
    if add_to_cart_match:
        reasons.append("add_to_cart_match")
    if view_match:
        reasons.append("view_match")
    if same_subcategory:
        reasons.append("same_subcategory")
    if same_brand:
        reasons.append("same_shop_brand_or_manufacturer")
    if best_seller_score > 0:
        reasons.append("best_seller")
    if avg_rating_score > 0:
        reasons.append("good_rating")
    return reasons


def _has_affinity(candidate: dict, anchors: list[dict]) -> bool:
    if not anchors:
        return False

    candidate_brand = _normalize_text(candidate.get("brand"))
    candidate_manufacturer = _normalize_text(candidate.get("manufacturer"))
    for anchor in anchors:
        if candidate.get("id") == anchor.get("id"):
            return True
        if candidate.get("subcategory_id") and candidate.get("subcategory_id") == anchor.get("subcategory_id"):
            return True
        if candidate.get("shop_id") and candidate.get("shop_id") == anchor.get("shop_id"):
            return True
        if candidate_brand and candidate_brand == _normalize_text(anchor.get("brand")):
            return True
        if candidate_manufacturer and candidate_manufacturer == _normalize_text(anchor.get("manufacturer")):
            return True
    return False


def _load_user_signals(user_id: str) -> dict[str, list[str]]:
    purchase_ids: list[str] = []
    add_to_cart_ids: list[str] = []
    view_ids: list[str] = []
    recent_purchase_ids: list[str] = []

    for order in _load_user_orders(user_id):
        order_items = _normalize_relation_list(order.get("order_items"))
        order_product_ids = [
            item.get("product_id")
            for item in order_items
            if item.get("product_id")
        ]
        purchase_ids.extend(order_product_ids)
        if _is_recent_timestamp(order.get("created_at")):
            recent_purchase_ids.extend(order_product_ids)

    for event in _load_user_events(user_id):
        product_id = event.get("product_id")
        if not product_id:
            continue
        event_type = event.get("event_type")
        if event_type in {"buy", "review"}:
            purchase_ids.append(product_id)
        elif event_type == "add_to_cart":
            add_to_cart_ids.append(product_id)
        elif event_type in {"view", "click", "search_click"}:
            view_ids.append(product_id)

    add_to_cart_ids.extend(_load_current_cart_product_ids(user_id))

    return {
        "purchase_ids": _unique_preserve_order(purchase_ids),
        "add_to_cart_ids": _unique_preserve_order(add_to_cart_ids),
        "view_ids": _unique_preserve_order(view_ids),
        "recent_purchase_ids": _unique_preserve_order(recent_purchase_ids),
    }


def _load_user_orders(user_id: str) -> list[dict]:
    try:
        response = (
            supabase.table("orders")
            .select("created_at,order_items(product_id,quantity)")
            .eq("user_id", user_id)
            .order("created_at", desc=True)
            .limit(MAX_USER_ORDERS)
            .execute()
        )
        return response.data or []
    except Exception:
        return []


def _load_user_events(user_id: str) -> list[dict]:
    try:
        response = (
            supabase.table("product_events")
            .select("product_id,event_type,created_at")
            .eq("user_id", user_id)
            .order("created_at", desc=True)
            .limit(MAX_USER_EVENTS)
            .execute()
        )
        return response.data or []
    except Exception:
        return []


def _load_current_cart_product_ids(user_id: str) -> list[str]:
    try:
        response = (
            supabase.table("cart_items")
            .select("product_id")
            .eq("user_id", user_id)
            .limit(100)
            .execute()
        )
        return [
            item.get("product_id")
            for item in response.data or []
            if item.get("product_id")
        ]
    except Exception:
        return []


def _load_active_product(product_id: str) -> dict:
    response = (
        _read_client()
        .table("products")
        .select(PRODUCT_SELECT)
        .eq("id", product_id)
        .eq("is_active", True)
        .maybe_single()
        .execute()
    )
    product = response.data
    if not product:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Product not found",
        )
    return product


def _load_products_by_ids(product_ids: list[str]) -> dict[str, dict]:
    product_ids = _unique_preserve_order(product_ids)
    if not product_ids:
        return {}

    try:
        response = (
            _read_client()
            .table("products")
            .select(PRODUCT_SELECT)
            .in_("id", product_ids)
            .execute()
        )
    except Exception:
        return {}

    return {
        product["id"]: product
        for product in response.data or []
        if product.get("id")
    }


def _load_candidate_products() -> list[dict]:
    response = (
        _read_client()
        .table("products")
        .select(PRODUCT_SELECT)
        .eq("is_active", True)
        .gt("stock", 0)
        .range(0, MAX_CANDIDATE_PRODUCTS - 1)
        .execute()
    )
    return response.data or []


def _load_best_seller_scores() -> dict[str, float]:
    try:
        response = (
            _read_client()
            .table("order_items")
            .select("product_id,quantity")
            .range(0, 999)
            .execute()
        )
    except Exception:
        return {}

    quantities: Counter[str] = Counter()
    for item in response.data or []:
        product_id = item.get("product_id")
        if not product_id:
            continue
        quantities[product_id] += max(int(item.get("quantity") or 1), 1)

    max_quantity = max(quantities.values(), default=0)
    if max_quantity <= 0:
        return {}
    return {
        product_id: quantity / max_quantity
        for product_id, quantity in quantities.items()
    }


def _load_rating_scores() -> dict[str, float]:
    try:
        response = (
            _read_client()
            .table("reviews")
            .select("product_id,rating,deleted_at")
            .range(0, 999)
            .execute()
        )
    except Exception:
        return {}

    rating_sums: defaultdict[str, float] = defaultdict(float)
    rating_counts: Counter[str] = Counter()
    for review in response.data or []:
        if review.get("deleted_at"):
            continue
        product_id = review.get("product_id")
        rating = review.get("rating")
        if not product_id or rating is None:
            continue
        rating_sums[product_id] += float(rating)
        rating_counts[product_id] += 1

    return {
        product_id: min((rating_sums[product_id] / count) / 5, 1)
        for product_id, count in rating_counts.items()
        if count > 0
    }


def _read_client():
    try:
        return get_service_supabase_client()
    except Exception:
        return supabase


def _normalize_relation_list(value):
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]


def _unique_preserve_order(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        if value and value not in seen:
            seen.add(value)
            result.append(value)
    return result


def _normalize_text(value: str | None) -> str:
    return (value or "").strip().lower()


def _is_recent_timestamp(value: str | None) -> bool:
    if not value:
        return False
    try:
        normalized = value.replace("Z", "+00:00")
        timestamp = datetime.fromisoformat(normalized)
    except ValueError:
        return False
    if timestamp.tzinfo is None:
        timestamp = timestamp.replace(tzinfo=UTC)
    cutoff = datetime.now(UTC) - timedelta(days=RECENT_PURCHASE_EXCLUSION_DAYS)
    return timestamp >= cutoff
