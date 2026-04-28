from pathlib import Path
from dotenv import load_dotenv
load_dotenv(Path(__file__).resolve().parent / ".env")

import logging
import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.tools.imagelingo.routes import auth, translate, webhook
from backend.tools.fitness import routes as fitness_routes

logger = logging.getLogger(__name__)

app = FastAPI(title="DaleToolMatrix API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://localhost:5173",
        os.getenv("FRONTEND_URL", ""),
    ],
    allow_origin_regex=r"https://.*\.vercel\.app",
    allow_methods=["*"],
    allow_headers=["*"],
)

# -- Tool: ImageLingo
app.include_router(auth.router, prefix="/api/imagelingo/auth")
app.include_router(translate.router, prefix="/api/imagelingo/translate")
app.include_router(webhook.router, prefix="/api/imagelingo/webhooks")

app.include_router(fitness_routes.router, prefix="/api")

# -- Future tools
# app.include_router(tool2.router, prefix="/api/tool2")


@app.on_event("startup")
async def _startup_env_check():
    logger.info("DaleToolMatrix starting up...")


@app.get("/health")
async def health():
    return {"status": "ok", "service": "daletoolmatrix"}
