"""GET /api/content-collector/sources — list all configured sources."""

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import get_content_collector_db
from ..fetchers.registry import all_metadata, get_registry
from ..models.source import Source

router = APIRouter()


@router.get("")
async def list_sources(db: AsyncSession = Depends(get_content_collector_db)):
    """Return DB-backed source rows when available, merged with fetcher metadata."""
    try:
        rows = (await db.execute(select(Source))).scalars().all()
    except Exception:
        rows = []

    by_slug = {r.slug: r for r in rows}
    out = []
    for meta in all_metadata():
        db_row = by_slug.get(meta["slug"])
        out.append(
            {
                **meta,
                "enabled": db_row.enabled if db_row else True,
                "last_fetched_at": db_row.last_fetched_at.isoformat() if db_row and db_row.last_fetched_at else None,
                "last_success_at": db_row.last_success_at.isoformat() if db_row and db_row.last_success_at else None,
                "last_error": db_row.last_error if db_row else None,
            }
        )
    return {"total": len(out), "sources": out}


@router.get("/registered")
async def list_registered():
    """Debug endpoint: what the fetcher registry sees right now."""
    return {"slugs": sorted(get_registry().keys())}
