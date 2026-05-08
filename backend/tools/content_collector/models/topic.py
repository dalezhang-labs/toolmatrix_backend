"""Topic + TopicItem models.

Topics are computed by clustering items within a rolling time window. Starts
simple (keyword / title similarity), upgradeable to embeddings later.
"""

from datetime import datetime
from typing import Optional

from sqlalchemy import (
    ARRAY,
    BigInteger,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column

from ..database import SCHEMA, Base


class Topic(Base):
    __tablename__ = "topics"
    __table_args__ = {"schema": SCHEMA}

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)

    label: Mapped[str] = mapped_column(Text, nullable=False)
    keywords: Mapped[list[str]] = mapped_column(ARRAY(String(64)), default=list, nullable=False)

    lang: Mapped[str] = mapped_column(String(4), nullable=False)

    item_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    source_diversity: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    total_score: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)

    first_item_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    last_item_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    window_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    window_end: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow, nullable=False
    )


class TopicItem(Base):
    __tablename__ = "topic_items"
    __table_args__ = {"schema": SCHEMA}

    topic_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey(f"{SCHEMA}.topics.id", ondelete="CASCADE"), primary_key=True
    )
    item_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey(f"{SCHEMA}.items.id", ondelete="CASCADE"), primary_key=True
    )
    similarity: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
