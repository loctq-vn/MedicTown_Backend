from collections import defaultdict
from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal
from zoneinfo import ZoneInfo

from fastapi import HTTPException, status

from app.database import supabase
from app.services.shop_service import get_my_shop


LOCAL_TZ = ZoneInfo("Asia/Ho_Chi_Minh")
PAGE_SIZE = 1000
GROSS_REVENUE_STATUSES = ["completed", "refunded"]


def get_revenue_dashboard(
    user_id: str,
    shop_id: str,
    from_date: date,
    to_date: date,
    group_by: str,
) -> dict:
    get_my_shop(user_id, shop_id)
    if from_date > to_date:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="from must be before or equal to to",
        )

    start_local, end_local = _date_range_to_local_bounds(from_date, to_date)
    now_local = datetime.now(LOCAL_TZ)
    today_start, today_end = _date_range_to_local_bounds(
        now_local.date(),
        now_local.date(),
    )
    month_start = datetime.combine(
        now_local.date().replace(day=1),
        time.min,
        tzinfo=LOCAL_TZ,
    )

    gross_payments = _list_shop_payments_by_paid_at(
        shop_id,
        start_local,
        end_local,
        GROSS_REVENUE_STATUSES,
    )
    refund_payments = _list_shop_payments_by_updated_at(
        shop_id,
        start_local,
        end_local,
        ["refunded"],
    )
    filtered_orders = _list_shop_orders_by_created_at(shop_id, start_local, end_local)

    return {
        "fixedKpis": {
            "todayRevenue": _completed_revenue_for_range(shop_id, today_start, today_end),
            "monthRevenue": _completed_revenue_for_range(shop_id, month_start, now_local),
        },
        "filteredSummary": _build_filtered_summary(
            gross_payments,
            refund_payments,
            filtered_orders,
        ),
        "chart": _build_chart(group_by, gross_payments),
        "paymentMethods": _build_payment_methods(gross_payments),
        "topProducts": _build_top_products(shop_id, gross_payments),
        "recentOrders": _build_recent_orders(shop_id),
    }


def get_revenue_daily_summary(
    user_id: str,
    shop_id: str,
    from_date: date | None = None,
    to_date: date | None = None,
) -> dict:
    get_my_shop(user_id, shop_id)
    if from_date and to_date and from_date > to_date:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="from must be before or equal to to",
        )

    start_local = None
    end_local = None
    if from_date or to_date:
        start_date = from_date or date(1970, 1, 1)
        end_date = to_date or datetime.now(LOCAL_TZ).date()
        start_local, end_local = _date_range_to_local_bounds(start_date, end_date)

    gross_payments = _list_shop_payments_by_paid_at_optional(
        shop_id,
        start_local,
        end_local,
        GROSS_REVENUE_STATUSES,
    )
    refund_payments = _list_shop_payments_by_updated_at_optional(
        shop_id,
        start_local,
        end_local,
        ["refunded"],
    )
    orders = _list_shop_orders_by_created_at_optional(shop_id, start_local, end_local)

    return {
        "items": _build_daily_summary_items(
            gross_payments,
            refund_payments,
            orders,
        ),
    }


def get_revenue_top_products(
    user_id: str,
    shop_id: str,
    from_date: date,
    to_date: date,
) -> list[dict]:
    get_my_shop(user_id, shop_id)
    if from_date > to_date:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="from must be before or equal to to",
        )

    start_local, end_local = _date_range_to_local_bounds(from_date, to_date)
    gross_payments = _list_shop_payments_by_paid_at(
        shop_id,
        start_local,
        end_local,
        GROSS_REVENUE_STATUSES,
    )
    return _build_top_products(shop_id, gross_payments)


def _date_range_to_local_bounds(from_date: date, to_date: date) -> tuple[datetime, datetime]:
    start_local = datetime.combine(from_date, time.min, tzinfo=LOCAL_TZ)
    end_local = datetime.combine(to_date + timedelta(days=1), time.min, tzinfo=LOCAL_TZ)
    return start_local, end_local


def _completed_revenue_for_range(
    shop_id: str,
    start_local: datetime,
    end_local: datetime,
) -> float:
    payments = _list_shop_payments_by_paid_at(
        shop_id,
        start_local,
        end_local,
        ["completed"],
    )
    return _money(sum(
        (_amount(payment.get("amount")) for payment in payments),
        Decimal("0"),
    ))


def _build_filtered_summary(
    gross_payments: list[dict],
    refund_payments: list[dict],
    filtered_orders: list[dict],
) -> dict:
    gross_revenue = sum(
        (_amount(payment.get("amount")) for payment in gross_payments),
        Decimal("0"),
    )
    refund_amount = sum(
        (_amount(payment.get("amount")) for payment in refund_payments),
        Decimal("0"),
    )
    order_status_counts = defaultdict(int)
    for order in filtered_orders:
        order_status_counts[(order.get("status") or "").lower()] += 1

    return {
        "grossRevenue": _money(gross_revenue),
        "refundAmount": _money(refund_amount),
        "netRevenue": _money(gross_revenue - refund_amount),
        "totalOrders": len(filtered_orders),
        "completedOrders": order_status_counts["completed"],
        "pendingOrders": order_status_counts["pending"],
        "cancelledOrders": order_status_counts["cancelled"],
    }


def _build_chart(group_by: str, gross_payments: list[dict]) -> dict:
    buckets: dict[str, dict] = {}
    for payment in gross_payments:
        paid_at = _parse_datetime(payment.get("paid_at"))
        if paid_at is None:
            continue

        period = _period_key(paid_at.astimezone(LOCAL_TZ), group_by)
        bucket = buckets.setdefault(
            period,
            {
                "period": period,
                "revenue": Decimal("0"),
                "order_ids": set(),
            },
        )
        bucket["revenue"] += _amount(payment.get("amount"))
        if payment.get("order_id"):
            bucket["order_ids"].add(payment["order_id"])

    return {
        "groupBy": group_by,
        "items": [
            {
                "period": period,
                "revenue": _money(bucket["revenue"]),
                "orderCount": len(bucket["order_ids"]),
            }
            for period, bucket in sorted(buckets.items())
        ],
    }


def _period_key(value: datetime, group_by: str) -> str:
    if group_by == "day":
        return value.date().isoformat()
    if group_by == "week":
        week_start = value.date() - timedelta(days=value.weekday())
        return week_start.isoformat()
    if group_by == "month":
        return value.date().replace(day=1).isoformat()
    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail="groupBy must be one of: day, week, month",
    )


def _build_payment_methods(gross_payments: list[dict]) -> list[dict]:
    total_revenue = sum(
        (_amount(payment.get("amount")) for payment in gross_payments),
        Decimal("0"),
    )
    methods: dict[str, dict] = {}
    for payment in gross_payments:
        method = payment.get("method") or "unknown"
        item = methods.setdefault(
            method,
            {
                "method": method,
                "revenue": Decimal("0"),
                "transactionCount": 0,
            },
        )
        item["revenue"] += _amount(payment.get("amount"))
        item["transactionCount"] += 1

    result = []
    for item in sorted(methods.values(), key=lambda value: value["revenue"], reverse=True):
        percentage = Decimal("0")
        if total_revenue > 0:
            percentage = (item["revenue"] / total_revenue) * Decimal("100")
        result.append(
            {
                "method": item["method"],
                "revenue": _money(item["revenue"]),
                "transactionCount": item["transactionCount"],
                "percentage": float(percentage.quantize(Decimal("0.01"))),
            }
        )
    return result


def _build_daily_summary_items(
    gross_payments: list[dict],
    refund_payments: list[dict],
    orders: list[dict],
) -> list[dict]:
    buckets: dict[str, dict] = {}

    for payment in gross_payments:
        paid_at = _parse_datetime(payment.get("paid_at"))
        if paid_at is None:
            continue

        bucket = _daily_bucket(buckets, paid_at)
        amount = _amount(payment.get("amount"))
        bucket["grossRevenue"] += amount

        method = payment.get("method") or "unknown"
        method_item = bucket["paymentMethods"].setdefault(
            method,
            {
                "method": method,
                "revenue": Decimal("0"),
                "transactionCount": 0,
            },
        )
        method_item["revenue"] += amount
        method_item["transactionCount"] += 1

    for payment in refund_payments:
        updated_at = _parse_datetime(payment.get("updated_at"))
        if updated_at is None:
            continue

        bucket = _daily_bucket(buckets, updated_at)
        bucket["refundAmount"] += _amount(payment.get("amount"))

    for order in orders:
        created_at = _parse_datetime(order.get("created_at"))
        if created_at is None:
            continue

        bucket = _daily_bucket(buckets, created_at)
        bucket["totalOrders"] += 1
        status_value = (order.get("status") or "").lower()
        if status_value == "completed":
            bucket["completedOrders"] += 1
        elif status_value == "confirmed":
            bucket["confirmedOrders"] += 1
        elif status_value == "shipping":
            bucket["shippingOrders"] += 1
        elif status_value == "cancelled":
            bucket["cancelledOrders"] += 1
        else:
            bucket["pendingOrders"] += 1

    items = []
    for day, bucket in sorted(buckets.items()):
        gross_revenue = bucket["grossRevenue"]
        refund_amount = bucket["refundAmount"]
        items.append(
            {
                "date": day,
                "grossRevenue": _money(gross_revenue),
                "refundAmount": _money(refund_amount),
                "netRevenue": _money(gross_revenue - refund_amount),
                "totalOrders": bucket["totalOrders"],
                "completedOrders": bucket["completedOrders"],
                "pendingOrders": bucket["pendingOrders"],
                "confirmedOrders": bucket["confirmedOrders"],
                "shippingOrders": bucket["shippingOrders"],
                "cancelledOrders": bucket["cancelledOrders"],
                "paymentMethods": _build_daily_payment_methods(bucket["paymentMethods"]),
            }
        )
    return items


def _daily_bucket(buckets: dict[str, dict], value: datetime) -> dict:
    day = value.astimezone(LOCAL_TZ).date().isoformat()
    return buckets.setdefault(
        day,
        {
            "grossRevenue": Decimal("0"),
            "refundAmount": Decimal("0"),
            "totalOrders": 0,
            "completedOrders": 0,
            "pendingOrders": 0,
            "confirmedOrders": 0,
            "shippingOrders": 0,
            "cancelledOrders": 0,
            "paymentMethods": {},
        },
    )


def _build_daily_payment_methods(methods: dict[str, dict]) -> list[dict]:
    total_revenue = sum(
        (item["revenue"] for item in methods.values()),
        Decimal("0"),
    )
    result = []
    for item in sorted(methods.values(), key=lambda value: value["revenue"], reverse=True):
        percentage = Decimal("0")
        if total_revenue > 0:
            percentage = (item["revenue"] / total_revenue) * Decimal("100")
        result.append(
            {
                "method": item["method"],
                "revenue": _money(item["revenue"]),
                "transactionCount": item["transactionCount"],
                "percentage": float(percentage.quantize(Decimal("0.01"))),
            }
        )
    return result


def _build_top_products(shop_id: str, gross_payments: list[dict]) -> list[dict]:
    paid_order_ids = sorted(
        {
            payment["order_id"]
            for payment in gross_payments
            if payment.get("order_id") and payment.get("status") == "completed"
        }
    )
    if not paid_order_ids:
        return []

    product_totals: dict[str, dict] = {}
    for order_id_chunk in _chunks(paid_order_ids, 100):
        order_items = _list_shop_order_items(shop_id, order_id_chunk)
        for item in order_items:
            product_id = item.get("product_id")
            if not product_id:
                continue

            total = product_totals.setdefault(
                product_id,
                {
                    "productId": product_id,
                    "productName": item.get("product_name"),
                    "productImage": item.get("product_image"),
                    "quantitySold": 0,
                    "revenue": Decimal("0"),
                },
            )
            quantity = int(item.get("quantity") or 0)
            total["quantitySold"] += quantity
            total["revenue"] += _amount(item.get("price")) * quantity

    top_products = sorted(
        product_totals.values(),
        key=lambda item: (item["quantitySold"], item["revenue"]),
        reverse=True,
    )[:5]
    stock_by_product_id = _get_product_stock_by_id(
        shop_id,
        [item["productId"] for item in top_products],
    )
    for item in top_products:
        item["stock"] = stock_by_product_id.get(item["productId"], 0)
        item["revenue"] = _money(item["revenue"])
    return top_products


def _build_recent_orders(shop_id: str) -> list[dict]:
    response = (
        supabase.table("orders")
        .select("id,shipping_name,total_amount,status,created_at,payments(*)")
        .eq("shop_id", shop_id)
        .order("created_at", desc=True)
        .limit(10)
        .execute()
    )

    recent_orders = []
    for order in response.data or []:
        payment = _latest_payment(order.get("payments"))
        recent_orders.append(
            {
                "orderId": order["id"],
                "customerName": order.get("shipping_name"),
                "amount": _money(_amount(order.get("total_amount"))),
                "paymentMethod": payment.get("method") if payment else None,
                "paymentStatus": payment.get("status") if payment else None,
                "orderStatus": order.get("status"),
                "createdAt": order.get("created_at"),
                "paidAt": payment.get("paid_at") if payment else None,
            }
        )
    return recent_orders


def _latest_payment(payments) -> dict | None:
    if payments is None:
        return None
    if isinstance(payments, dict):
        return payments
    if not isinstance(payments, list) or not payments:
        return None
    return sorted(
        payments,
        key=lambda payment: (
            payment.get("paid_at")
            or payment.get("updated_at")
            or payment.get("created_at")
            or ""
        ),
        reverse=True,
    )[0]


def _list_shop_payments_by_paid_at(
    shop_id: str,
    start_local: datetime,
    end_local: datetime,
    statuses: list[str],
) -> list[dict]:
    return _paged(
        lambda: _shop_payments_query(shop_id, statuses)
        .gte("paid_at", _to_utc_iso(start_local))
        .lt("paid_at", _to_utc_iso(end_local))
        .order("paid_at"),
    )


def _list_shop_payments_by_paid_at_optional(
    shop_id: str,
    start_local: datetime | None,
    end_local: datetime | None,
    statuses: list[str],
) -> list[dict]:
    def query_factory():
        query = _shop_payments_query(shop_id, statuses)
        if start_local is not None:
            query = query.gte("paid_at", _to_utc_iso(start_local))
        if end_local is not None:
            query = query.lt("paid_at", _to_utc_iso(end_local))
        return query.order("paid_at")

    return _paged(query_factory)


def _list_shop_payments_by_updated_at(
    shop_id: str,
    start_local: datetime,
    end_local: datetime,
    statuses: list[str],
) -> list[dict]:
    return _paged(
        lambda: _shop_payments_query(shop_id, statuses)
        .gte("updated_at", _to_utc_iso(start_local))
        .lt("updated_at", _to_utc_iso(end_local))
        .order("updated_at"),
    )


def _list_shop_payments_by_updated_at_optional(
    shop_id: str,
    start_local: datetime | None,
    end_local: datetime | None,
    statuses: list[str],
) -> list[dict]:
    def query_factory():
        query = _shop_payments_query(shop_id, statuses)
        if start_local is not None:
            query = query.gte("updated_at", _to_utc_iso(start_local))
        if end_local is not None:
            query = query.lt("updated_at", _to_utc_iso(end_local))
        return query.order("updated_at")

    return _paged(query_factory)


def _shop_payments_query(shop_id: str, statuses: list[str]):
    query = (
        supabase.table("payments")
        .select("id,order_id,method,amount,status,paid_at,updated_at,orders!inner(id,shop_id)")
        .eq("orders.shop_id", shop_id)
    )
    if len(statuses) == 1:
        return query.eq("status", statuses[0])
    return query.in_("status", statuses)


def _list_shop_orders_by_created_at(
    shop_id: str,
    start_local: datetime,
    end_local: datetime,
) -> list[dict]:
    return _paged(
        lambda: supabase.table("orders")
        .select("id,status,created_at")
        .eq("shop_id", shop_id)
        .gte("created_at", _to_utc_iso(start_local))
        .lt("created_at", _to_utc_iso(end_local))
        .order("created_at"),
    )


def _list_shop_orders_by_created_at_optional(
    shop_id: str,
    start_local: datetime | None,
    end_local: datetime | None,
) -> list[dict]:
    def query_factory():
        query = (
            supabase.table("orders")
            .select("id,status,created_at")
            .eq("shop_id", shop_id)
        )
        if start_local is not None:
            query = query.gte("created_at", _to_utc_iso(start_local))
        if end_local is not None:
            query = query.lt("created_at", _to_utc_iso(end_local))
        return query.order("created_at")

    return _paged(query_factory)


def _list_shop_order_items(shop_id: str, order_ids: list[str]) -> list[dict]:
    return _paged(
        lambda: supabase.table("order_items")
        .select(
            "order_id,product_id,product_name,product_image,price,quantity,"
            "orders!inner(id,shop_id)"
        )
        .eq("orders.shop_id", shop_id)
        .in_("order_id", order_ids),
    )


def _get_product_stock_by_id(shop_id: str, product_ids: list[str]) -> dict[str, int]:
    if not product_ids:
        return {}

    stock_by_id: dict[str, int] = {}
    for product_id_chunk in _chunks(product_ids, 100):
        response = (
            supabase.table("products")
            .select("id,stock")
            .eq("shop_id", shop_id)
            .in_("id", product_id_chunk)
            .execute()
        )
        for product in response.data or []:
            product_id = product.get("id")
            if product_id:
                stock_by_id[product_id] = int(product.get("stock") or 0)
    return stock_by_id


def _paged(query_factory) -> list[dict]:
    rows: list[dict] = []
    offset = 0
    while True:
        response = query_factory().range(offset, offset + PAGE_SIZE - 1).execute()
        page = response.data or []
        rows.extend(page)
        if len(page) < PAGE_SIZE:
            return rows
        offset += PAGE_SIZE


def _to_utc_iso(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat()


def _parse_datetime(value) -> datetime | None:
    if not value:
        return None
    if isinstance(value, datetime):
        parsed = value
    else:
        try:
            parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        except ValueError:
            return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed


def _amount(value) -> Decimal:
    if value is None:
        return Decimal("0")
    return Decimal(str(value))


def _money(value: Decimal) -> float:
    return float(value.quantize(Decimal("0.01")))


def _chunks(values: list[str], size: int):
    for index in range(0, len(values), size):
        yield values[index:index + size]
