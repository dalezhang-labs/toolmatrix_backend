"""Topic clustering over a rolling time window.

Design choices:
- Uses scikit-learn's TF-IDF with char n-grams (analyzer='char_wb', n=2-4).
  Works for both Chinese and English without a tokenizer, handles typos.
- Clusters with DBSCAN on cosine distance so we don't need to guess k.
- Runs per-language (zh / en separately) — cross-language clustering rarely
  produces meaningful groups, and the metric behaves better within one script.
- Called periodically by the scheduler; writes Topic + TopicItem rows, wipes
  previous topics in the window before rewriting (idempotent).

If scikit-learn isn't available (unlikely on Railway but keep robust), we
degrade to a simple substring-overlap grouping.
"""

from __future__ import annotations

import logging
import re
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Iterable

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import session_factory
from ..models.item import Item, ItemSnapshot
from ..models.source import Source
from ..models.topic import Topic, TopicItem

logger = logging.getLogger(__name__)

try:
    from sklearn.cluster import DBSCAN
    from sklearn.feature_extraction.text import TfidfVectorizer

    _HAS_SKLEARN = True
except Exception:  # pragma: no cover
    _HAS_SKLEARN = False


# ------------------------------------------------------------------ helpers
_NON_WORD = re.compile(r"[\s\W_]+", re.UNICODE)


def _tokens(text: str) -> list[str]:
    """Rough bag-of-words for keyword extraction (not for clustering)."""
    if not text:
        return []
    cleaned = _NON_WORD.sub(" ", text).strip()
    return [t for t in cleaned.split() if len(t) >= 2]


_STOPWORDS_EN = {
    "the", "and", "for", "with", "from", "that", "this", "you", "your",
    "how", "why", "what", "when", "why", "are", "not", "has", "have",
    "was", "were", "been", "its", "their", "than", "they", "them",
    "will", "would", "could", "should", "can", "may", "might", "about",
    "into", "onto", "over", "under", "more", "most", "some", "any",
    "all", "out", "new",
}
_STOPWORDS_ZH = {
    "的", "了", "是", "在", "我", "有", "和", "就", "不", "人",
    "都", "一", "一个", "也", "很", "到", "说", "要", "去", "你",
    "会", "着", "没", "看", "好", "这", "那", "里", "但", "被",
}


def _top_keywords(titles: Iterable[str], lang: str, k: int = 6) -> list[str]:
    stop = _STOPWORDS_EN if lang == "en" else _STOPWORDS_ZH
    counter: Counter[str] = Counter()
    for t in titles:
        for w in _tokens(t):
            wl = w.lower() if lang == "en" else w
            if wl in stop:
                continue
            counter[wl] += 1
    return [w for w, _ in counter.most_common(k)]


# ------------------------------------------------------------------ core


@dataclass
class _ItemRow:
    item_id: int
    source_id: int
    title: str
    first_seen_at: datetime
    hot_score: float
    source_weight: float


async def _load_window(session: AsyncSession, lang: str, days: int) -> list[_ItemRow]:
    since = datetime.now(timezone.utc) - timedelta(days=days)

    # For each item keep only its latest snapshot's hot_score
    stmt = (
        select(
            Item.id,
            Item.source_id,
            Item.title,
            Item.first_seen_at,
            ItemSnapshot.hot_score,
            Source.weight,
        )
        .join(Source, Source.id == Item.source_id)
        .join(ItemSnapshot, ItemSnapshot.item_id == Item.id)
        .where(Source.lang == lang)
        .where(Item.first_seen_at >= since)
        .order_by(Item.id, ItemSnapshot.captured_at.desc())
    )
    rows = (await session.execute(stmt)).all()

    seen: set[int] = set()
    out: list[_ItemRow] = []
    for (iid, sid, title, first_seen, hot_score, weight) in rows:
        if iid in seen:
            continue
        seen.add(iid)
        out.append(
            _ItemRow(
                item_id=int(iid),
                source_id=int(sid),
                title=title or "",
                first_seen_at=first_seen,
                hot_score=float(hot_score or 0),
                source_weight=float(weight or 1.0),
            )
        )
    return out


def _cluster_with_sklearn(texts: list[str]) -> list[int]:
    """Return a cluster label per text. -1 means noise (own cluster)."""
    if len(texts) < 3:
        return [-1] * len(texts)

    # char_wb 2-4 grams handle both Chinese and English robustly
    vec = TfidfVectorizer(
        analyzer="char_wb",
        ngram_range=(2, 4),
        min_df=2,
        max_features=20000,
    )
    try:
        X = vec.fit_transform(texts)
    except ValueError:
        return [-1] * len(texts)

    # eps=0.45 tuned from real data — tighter than sklearn defaults so we
    # don't merge loosely-related headlines. min_samples=3 means a topic must
    # have at least 3 stories to count.
    model = DBSCAN(metric="cosine", eps=0.45, min_samples=3)
    labels = model.fit_predict(X)
    return labels.tolist()


def _cluster_fallback(texts: list[str]) -> list[int]:
    """Degenerate grouper: two texts cluster iff they share >=4 unique chars
    of length 3+. Only used if sklearn isn't installed."""
    labels = [-1] * len(texts)
    next_label = 0

    def grams(t: str) -> set[str]:
        t = t.lower()
        return {t[i : i + 3] for i in range(len(t) - 2)}

    buckets = [grams(t) for t in texts]
    for i in range(len(texts)):
        if labels[i] != -1:
            continue
        group_open = False
        for j in range(i + 1, len(texts)):
            if labels[j] != -1:
                continue
            if len(buckets[i] & buckets[j]) >= 4:
                if not group_open:
                    labels[i] = next_label
                    group_open = True
                labels[j] = next_label
        if group_open:
            next_label += 1
    return labels


async def _cluster_for_lang(
    session: AsyncSession, lang: str, days: int = 7
) -> int:
    rows = await _load_window(session, lang, days)
    if not rows:
        return 0

    texts = [r.title for r in rows]
    cluster_fn = _cluster_with_sklearn if _HAS_SKLEARN else _cluster_fallback
    labels = cluster_fn(texts)

    # Group rows by label (ignore noise)
    groups: dict[int, list[_ItemRow]] = {}
    for row, lbl in zip(rows, labels):
        if lbl < 0:
            continue
        groups.setdefault(lbl, []).append(row)

    if not groups:
        return 0

    now = datetime.now(timezone.utc)
    window_start = now - timedelta(days=days)

    # Wipe previous topics for this language so we always have a fresh snapshot.
    # Cascades delete topic_items too.
    old_ids = (
        await session.execute(
            select(Topic.id).where(Topic.lang == lang).where(Topic.window_end >= window_start)
        )
    ).scalars().all()
    if old_ids:
        await session.execute(delete(Topic).where(Topic.id.in_(list(old_ids))))

    created = 0
    for members in groups.values():
        if len(members) < 3:
            continue
        titles = [m.title for m in members]
        kw = _top_keywords(titles, lang)
        label = kw[0] if kw else titles[0][:32]

        source_diversity = len({m.source_id for m in members})
        total_score = sum(m.hot_score * m.source_weight for m in members)

        topic = Topic(
            label=label,
            keywords=kw,
            lang=lang,
            item_count=len(members),
            source_diversity=source_diversity,
            total_score=total_score,
            first_item_at=min(m.first_seen_at for m in members),
            last_item_at=max(m.first_seen_at for m in members),
            window_start=window_start,
            window_end=now,
        )
        session.add(topic)
        await session.flush()

        for m in members:
            session.add(
                TopicItem(
                    topic_id=topic.id,
                    item_id=m.item_id,
                    similarity=1.0,  # refined later if we add embeddings
                )
            )

        created += 1

    return created


async def recluster_all(days: int = 7) -> dict:
    """Entry point invoked by the scheduler."""
    factory = session_factory()
    result: dict[str, int] = {}
    async with factory() as session:
        try:
            for lang in ("zh", "en"):
                result[lang] = await _cluster_for_lang(session, lang, days)
            await session.commit()
        except Exception:
            await session.rollback()
            raise
    logger.info("content_collector: reclustered topics %s", result)
    return result
