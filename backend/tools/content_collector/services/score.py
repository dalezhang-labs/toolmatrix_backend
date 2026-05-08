"""Normalize raw hotness values into a 0-100 hot_score.

Per-batch min-max within a source, blended with source.weight so cross-source
comparisons are meaningful. Kept simple; we can swap in a better formula once
we see real distributions.
"""

from __future__ import annotations

import math
from typing import Iterable

from ..fetchers.base import NewsItem


def _log1p_safe(x: float | None) -> float:
    if x is None or x <= 0:
        return 0.0
    return math.log1p(x)


def normalize_batch(items: Iterable[NewsItem], source_weight: float) -> list[tuple[NewsItem, float]]:
    """Return [(item, hot_score 0-100)]. Uses log1p of hot_raw, min-max within
    the batch.

    Note: `source_weight` is NOT applied here — it belongs in cross-source
    ranking at query time (ORDER BY hot_score * source.weight). Keeping
    hot_score as a pure 0-100 within-source signal preserves resolution.
    """
    _ = source_weight  # reserved for future per-item weighting
    items = list(items)
    if not items:
        return []

    logs = [_log1p_safe(it.hot_raw) for it in items]
    max_log = max(logs) or 1.0

    out: list[tuple[NewsItem, float]] = []
    for it, log_val in zip(items, logs):
        if it.hot_raw is None:
            # Rank-based fallback: higher rank position → lower score
            rank = it.rank or (len(items))
            base = max(0.0, 1.0 - (rank - 1) / max(1, len(items)))
        else:
            base = log_val / max_log
        score = round(base * 100.0, 3)
        out.append((it, min(score, 100.0)))
    return out
