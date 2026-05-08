"""Public helper that main.py calls to mount all content_collector routes."""

from fastapi import FastAPI

from .routes import admin, digests, items, sources, topics


def include_content_collector_routes(app: FastAPI) -> None:
    app.include_router(
        items.router, prefix="/api/content-collector/items", tags=["content-collector"]
    )
    app.include_router(
        sources.router, prefix="/api/content-collector/sources", tags=["content-collector"]
    )
    app.include_router(
        topics.router, prefix="/api/content-collector/topics", tags=["content-collector"]
    )
    app.include_router(
        digests.router, prefix="/api/content-collector/digests", tags=["content-collector"]
    )
    app.include_router(
        admin.router, prefix="/api/content-collector/admin", tags=["content-collector"]
    )
