"""Topics + Events read APIs."""

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import get_content_collector_db
from ..models.event import Event, EventItem
from ..models.item import Item, ItemSnapshot
from ..models.source import Source
from ..models.topic import Topic, TopicItem

router = APIRouter()


@router.get("")
async def list_topics(
    lang: Optional[str] = Query(None, description="zh | en"),
    limit: int = Query(30, ge=1, le=100),
    db: AsyncSession = Depends(get_content_collector_db),
):
    q = select(Topic).order_by(
        desc(Topic.total_score * Topic.source_diversity)
    ).limit(limit)
    if lang:
        q = q.where(Topic.lang == lang)
    topics = (await db.execute(q)).scalars().all()

    return {
        "total": len(topics),
        "topics": [
            {
                "id": t.id,
                "label": t.label,
                "keywords": t.keywords,
                "lang": t.lang,
                "item_count": t.item_count,
                "source_diversity": t.source_diversity,
                "total_score": t.total_score,
                "first_item_at": t.first_item_at.isoformat() if t.first_item_at else None,
                "last_item_at": t.last_item_at.isoformat() if t.last_item_at else None,
                "window_end": t.window_end.isoformat(),
            }
            for t in topics
        ],
    }


@router.get("/{topic_id}")
async def topic_detail(
    topic_id: int,
    db: AsyncSession = Depends(get_content_collector_db),
):
    topic = (
        await db.execute(select(Topic).where(Topic.id == topic_id))
    ).scalar_one_or_none()
    if not topic:
        raise HTTPException(404, "topic not found")

    rows = (
        await db.execute(
            select(
                Item.id,
                Item.title,
                Item.url,
                Item.first_seen_at,
                Source.slug,
                Source.name,
                Source.lang.label("source_lang"),
                TopicItem.similarity,
                ItemSnapshot.hot_score,
                ItemSnapshot.hot_raw,
            )
            .join(Source, Source.id == Item.source_id)
            .join(TopicItem, TopicItem.item_id == Item.id)
            .outerjoin(ItemSnapshot, ItemSnapshot.item_id == Item.id)
            .where(TopicItem.topic_id == topic_id)
            .order_by(Item.first_seen_at.desc(), ItemSnapshot.captured_at.desc())
        )
    ).mappings().all()

    # Dedup by item id (we may have many snapshots per item)
    seen: set[int] = set()
    items: list[dict] = []
    for r in rows:
        if r["id"] in seen:
            continue
        seen.add(r["id"])
        items.append(
            {
                "id": r["id"],
                "title": r["title"],
                "url": r["url"],
                "source": {"slug": r["slug"], "name": r["name"], "lang": r["source_lang"]},
                "hot_score": r["hot_score"],
                "hot_raw": r["hot_raw"],
                "first_seen_at": r["first_seen_at"].isoformat() if r["first_seen_at"] else None,
            }
        )

    return {
        "topic": {
            "id": topic.id,
            "label": topic.label,
            "keywords": topic.keywords,
            "lang": topic.lang,
            "item_count": topic.item_count,
            "source_diversity": topic.source_diversity,
            "total_score": topic.total_score,
        },
        "items": items,
    }


@router.get("/events/list")
async def list_events(
    active_only: bool = Query(True),
    lang: Optional[str] = Query(None),
    limit: int = Query(30, ge=1, le=100),
    db: AsyncSession = Depends(get_content_collector_db),
):
    q = select(Event).order_by(desc(Event.peak_score)).limit(limit)
    if active_only:
        q = q.where(Event.active.is_(True))
    if lang:
        q = q.where(Event.lang == lang)
    events = (await db.execute(q)).scalars().all()

    return {
        "total": len(events),
        "events": [
            {
                "id": e.id,
                "signature": e.signature,
                "label": e.label,
                "keywords": e.keywords,
                "lang": e.lang,
                "summary": e.summary,
                "first_detected_at": e.first_detected_at.isoformat(),
                "last_seen_at": e.last_seen_at.isoformat(),
                "source_count": e.source_count,
                "peak_score": e.peak_score,
                "item_count": e.item_count,
                "active": e.active,
            }
            for e in events
        ],
    }


@router.get("/events/{event_id}")
async def event_detail(
    event_id: int,
    db: AsyncSession = Depends(get_content_collector_db),
):
    event = (
        await db.execute(select(Event).where(Event.id == event_id))
    ).scalar_one_or_none()
    if not event:
        raise HTTPException(404, "event not found")

    rows = (
        await db.execute(
            select(
                Item.id,
                Item.title,
                Item.url,
                Item.first_seen_at,
                Source.slug,
                Source.name,
                Source.lang.label("source_lang"),
                ItemSnapshot.hot_score,
                ItemSnapshot.hot_raw,
            )
            .join(Source, Source.id == Item.source_id)
            .join(EventItem, EventItem.item_id == Item.id)
            .outerjoin(ItemSnapshot, ItemSnapshot.item_id == Item.id)
            .where(EventItem.event_id == event_id)
            .order_by(ItemSnapshot.hot_score.desc().nulls_last())
        )
    ).mappings().all()

    seen: set[int] = set()
    items: list[dict] = []
    for r in rows:
        if r["id"] in seen:
            continue
        seen.add(r["id"])
        items.append(
            {
                "id": r["id"],
                "title": r["title"],
                "url": r["url"],
                "source": {"slug": r["slug"], "name": r["name"], "lang": r["source_lang"]},
                "hot_score": r["hot_score"],
                "hot_raw": r["hot_raw"],
                "first_seen_at": r["first_seen_at"].isoformat() if r["first_seen_at"] else None,
            }
        )

    return {
        "event": {
            "id": event.id,
            "label": event.label,
            "keywords": event.keywords,
            "lang": event.lang,
            "summary": event.summary,
            "first_detected_at": event.first_detected_at.isoformat(),
            "last_seen_at": event.last_seen_at.isoformat(),
            "source_count": event.source_count,
            "peak_score": event.peak_score,
            "item_count": event.item_count,
            "active": event.active,
        },
        "items": items,
    }
