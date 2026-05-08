"""Event + EventItem models.

An Event represents an influential story: something crossing ≥3 independent
sources with enough cumulative heat. Events are identified by a `signature`
(stable keyword-based fingerprint) so re-detection updates the existing row
instead of inserting duplicates.

Events do NOT reference Topic rows directly — clustering re-runs wipe & rebuild
the topic set, which would orphan events. Instead we snapshot the essentials
(label/keywords/lang) onto the event, and link to member items via event_items.
"""

from datetime import datetime

from sqlalchemy import (
    ARRAY,
    BigInteger,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    Index,
)
from sqlalchemy.orm import Mapped, mapped_column

from ..database import SCHEMA, Base


class Event(Base):
    __tablename__ = "events"
    __table_args__ = (
        Index("ix_events_last_seen_at", "last_seen_at"),
        Index("ix_events_lang", "lang"),
        {"schema": SCHEMA},
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)

    # Stable identity — e.g. sha1(lang + '|' + top_keyword)
    signature: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)

    label: Mapped[str] = mapped_column(Text, nullable=False)
    keywords: Mapped[list[str]] = mapped_column(
        ARRAY(String(64)), default=list, nullable=False
    )
    lang: Mapped[str] = mapped_column(String(4), nullable=False)
    summary: Mapped[str] = mapped_column(Text, nullable=False)

    first_detected_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow, nullable=False
    )
    last_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
    )

    source_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    peak_score: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    item_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class EventItem(Base):
    __tablename__ = "event_items"
    __table_args__ = (
        Index("ix_event_items_item", "item_id"),
        {"schema": SCHEMA},
    )

    event_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey(f"{SCHEMA}.events.id", ondelete="CASCADE"),
        primary_key=True,
    )
    item_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey(f"{SCHEMA}.items.id", ondelete="CASCADE"),
        primary_key=True,
    )
    attached_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow, nullable=False
    )
