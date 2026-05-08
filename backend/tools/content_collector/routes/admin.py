"""Admin endpoints: manually trigger a fetch, useful for dev and troubleshooting.

These are intentionally not behind auth right now — add basic auth before
exposing publicly.
"""

from fastapi import APIRouter, HTTPException, Query

from ..fetchers.registry import get_fetcher, get_registry
from ..services.cluster import recluster_all
from ..services.digest import generate_digest
from ..services.events import detect_events
from ..services.ingest import run_source

router = APIRouter()


@router.post("/fetch/{slug}")
async def trigger_fetch(slug: str):
    if slug == "all":
        results = []
        for s in get_registry().keys():
            results.append(await run_source(s))
        return {"total": len(results), "results": results}

    if not get_fetcher(slug):
        raise HTTPException(404, f"unknown source: {slug}")
    return await run_source(slug)


@router.post("/recluster")
async def trigger_recluster(days: int = 7):
    return await recluster_all(days=days)


@router.post("/detect-events")
async def trigger_detect_events():
    return await detect_events()


@router.post("/generate-digest")
async def trigger_generate_digest(
    date: str | None = Query(None, description="YYYY-MM-DD; default = yesterday in ET"),
):
    """Generate or regenerate a digest for a given calendar day."""
    target = None
    if date:
        from datetime import date as _date

        try:
            target = _date.fromisoformat(date)
        except ValueError:
            raise HTTPException(400, "invalid date — use YYYY-MM-DD")
    return await generate_digest(target)
