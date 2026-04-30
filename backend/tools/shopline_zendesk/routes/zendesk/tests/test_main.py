from fastapi import FastAPI
from pydantic import BaseModel
import sys

app = FastAPI(title="Shopline API Test", version="1.0.0")

class HealthResponse(BaseModel):
    status: str
    python_version: str
    message: str

@app.get("/")
async def root():
    return {"message": "Shopline FastAPI is running!"}

@app.get("/health", response_model=HealthResponse)
async def health():
    return HealthResponse(
        status="healthy",
        python_version=sys.version,
        message="Python 3.13 + FastAPI + Pydantic 2.x working!"
    )

@app.get("/test")
async def test():
    return {
        "fastapi": "✅ Working",
        "pydantic": "✅ Working", 
        "python": f"✅ {sys.version}",
        "message": "All systems operational!"
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=10000) 