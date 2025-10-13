from fastapi import FastAPI


app = FastAPI()

@app.get("/")
async def get_index():
    return {"message": "Hello World"}
