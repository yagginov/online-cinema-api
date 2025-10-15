from fastapi import FastAPI

from routes import movie_router
from routes.accounts import router as accounts_router
from routes.profiles import router as profiles_router

app = FastAPI()

api_version_prefix = "/api/v1"


@app.get("/")
async def get_index():
    return {"message": "Hello World"}


app.include_router(movie_router, prefix=f"{api_version_prefix}/cinema", tags=["cinema"])
app.include_router(accounts_router, prefix=f"{api_version_prefix}/accounts", tags=["accounts"])
app.include_router(profiles_router, prefix=f"{api_version_prefix}/profiles", tags=["profiles"])
