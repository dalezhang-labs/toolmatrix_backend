"""OmnigaTech health check endpoint."""

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.responses import JSONResponse

from backend.tools.omnigatech.database import get_omnigatech_db

router = APIRouter()


@router.get("/health")
async def omnigatech_health(db: AsyncSession = Depends(get_omnigatech_db)):
    """Health check that verifies the omnigatech DB connection."""
    try:
        await db.execute(text("SELECT 1"))
        return {
            "status": "ok",
            "service": "omnigatech",
            "database": "connected",
        }
    except Exception:
        return JSONResponse(
            status_code=503,
            content={
                "status": "degraded",
                "service": "omnigatech",
                "database": "disconnected",
            },
        )
