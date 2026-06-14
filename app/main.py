from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.routers import (
    addresses,
    ads,
    auth,
    cart,
    chat,
    notifications,
    orders,
    payments,
    products,
    revenue,
    reviews,
    shops,
    users,
)


app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="Backend API trung gian cho ung dung MedicTown Android.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
def health_check() -> dict[str, str]:
    return {"status": "ok", "service": settings.app_name}


app.include_router(auth.router, prefix="/api/auth", tags=["Auth"])
app.include_router(users.router, prefix="/api/users", tags=["Users"])
app.include_router(addresses.router, prefix="/api/address", tags=["Address"])
app.include_router(ads.router, prefix="/api/ads", tags=["Advertisements"])
app.include_router(cart.router, prefix="/api/cart_items", tags=["Cart"])
app.include_router(chat.router, prefix="/api/chat", tags=["Chat"])
app.include_router(products.router, prefix="/api/products", tags=["Products"])
app.include_router(
    notifications.router,
    prefix="/api/notifications",
    tags=["Notifications"],
)
app.include_router(orders.router, prefix="/api/orders", tags=["Orders"])
app.include_router(payments.router, prefix="/api/payments", tags=["Payments"])
app.include_router(revenue.router, prefix="/api/revenue", tags=["Revenue"])
app.include_router(reviews.router, prefix="/api/reviews", tags=["Reviews"])
app.include_router(shops.router, prefix="/api/shops", tags=["Shops"])
