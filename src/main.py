from fastapi import FastAPI

from routes import movie_router

app = FastAPI()

API_VERSION_PREFIX = "/api/v1"

@app.get("/")
async def get_index():
    return {"message": "Hello World"}



app.include_router(movie_router, prefix=f"{API_VERSION_PREFIX}/cinema", tags=["cinema"])
