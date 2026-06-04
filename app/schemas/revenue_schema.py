from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class RevenueFixedKpis(BaseModel):
    today_revenue: float = Field(0, alias="todayRevenue")
    month_revenue: float = Field(0, alias="monthRevenue")

    model_config = ConfigDict(populate_by_name=True)


class RevenueFilteredSummary(BaseModel):
    gross_revenue: float = Field(0, alias="grossRevenue")
    refund_amount: float = Field(0, alias="refundAmount")
    net_revenue: float = Field(0, alias="netRevenue")
    total_orders: int = Field(0, alias="totalOrders")
    completed_orders: int = Field(0, alias="completedOrders")
    pending_orders: int = Field(0, alias="pendingOrders")
    cancelled_orders: int = Field(0, alias="cancelledOrders")

    model_config = ConfigDict(populate_by_name=True)


class RevenueChartItem(BaseModel):
    period: str
    revenue: float = 0
    order_count: int = Field(0, alias="orderCount")

    model_config = ConfigDict(populate_by_name=True)


class RevenueChart(BaseModel):
    group_by: Literal["day", "week", "month"] = Field(alias="groupBy")
    items: list[RevenueChartItem] = Field(default_factory=list)

    model_config = ConfigDict(populate_by_name=True)


class RevenuePaymentMethod(BaseModel):
    method: str
    revenue: float = 0
    transaction_count: int = Field(0, alias="transactionCount")
    percentage: float = 0

    model_config = ConfigDict(populate_by_name=True)


class RevenueTopProduct(BaseModel):
    product_id: str = Field(alias="productId")
    product_name: str | None = Field(default=None, alias="productName")
    product_image: str | None = Field(default=None, alias="productImage")
    quantity_sold: int = Field(0, alias="quantitySold")
    revenue: float = 0

    model_config = ConfigDict(populate_by_name=True)


class RevenueRecentOrder(BaseModel):
    order_id: str = Field(alias="orderId")
    customer_name: str | None = Field(default=None, alias="customerName")
    amount: float = 0
    payment_method: str | None = Field(default=None, alias="paymentMethod")
    payment_status: str | None = Field(default=None, alias="paymentStatus")
    order_status: str | None = Field(default=None, alias="orderStatus")
    created_at: datetime | None = Field(default=None, alias="createdAt")
    paid_at: datetime | None = Field(default=None, alias="paidAt")

    model_config = ConfigDict(populate_by_name=True)


class RevenueDashboard(BaseModel):
    fixed_kpis: RevenueFixedKpis = Field(alias="fixedKpis")
    filtered_summary: RevenueFilteredSummary = Field(alias="filteredSummary")
    chart: RevenueChart
    payment_methods: list[RevenuePaymentMethod] = Field(
        default_factory=list,
        alias="paymentMethods",
    )
    top_products: list[RevenueTopProduct] = Field(default_factory=list, alias="topProducts")
    recent_orders: list[RevenueRecentOrder] = Field(default_factory=list, alias="recentOrders")

    model_config = ConfigDict(populate_by_name=True)
