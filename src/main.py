from fastapi import FastAPI

from routes import cart_router, favorites_router, movie_router, order_router, payment_router
from routes.accounts import router as accounts_router
from routes.profiles import router as profiles_router

app = FastAPI(
    title="Online Cinema API",
    description="REST API for online cinema with movies, orders, and user management",
    version="1.0.0",
)

api_version_prefix = "/api/v1"


@app.get("/")
async def get_index():
    """Health check endpoint"""
    return {"message": "Online Cinema API is running. Visit /docs for documentation."}


app.include_router(movie_router, prefix=f"{api_version_prefix}/cinema", tags=["cinema"])
app.include_router(order_router, prefix=f"{api_version_prefix}", tags=["orders"])
app.include_router(payment_router, prefix=f"{api_version_prefix}", tags=["payments"])
app.include_router(accounts_router, prefix=f"{api_version_prefix}/accounts", tags=["accounts"])
app.include_router(profiles_router, prefix=f"{api_version_prefix}/profiles", tags=["profiles"])
app.include_router(cart_router, prefix=f"{api_version_prefix}", tags=["cart"])
app.include_router(favorites_router, prefix=f"{api_version_prefix}", tags=["favorites"])
