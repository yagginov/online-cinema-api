from fastapi import FastAPI
from routes.accounts import router as accounts_router


from routes import movie_router

app = FastAPI()

<<<<<<< HEAD
API_VERSION_PREFIX = "/api/v1"

=======
api_version_prefix = "/api/v1"
>>>>>>> 1115745 (feature: add accounts router with versioned API prefix for modular routing)

@app.get("/")
async def get_index():
    return {"message": "Hello World"}

<<<<<<< HEAD

app.include_router(movie_router, prefix=f"{API_VERSION_PREFIX}/cinema", tags=["cinema"])
=======
app.include_router(accounts_router, prefix=f"{api_version_prefix}/accounts", tags=["accounts"])
>>>>>>> 1115745 (feature: add accounts router with versioned API prefix for modular routing)
