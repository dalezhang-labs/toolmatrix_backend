"""Content Collector tool.

Aggregates hot posts, trending topics, and influential events from multiple
Chinese and English sources (Weibo, Zhihu, Bilibili, Hacker News, Reddit, etc.)
into a unified 7-day hot dashboard.

Architecture:
- fetchers/       one file per source, auto-discovered by registry
- services/       ingest / score / scheduler
- models/         SQLAlchemy models bound to the `content_collector` schema
- routes/         FastAPI endpoints under /api/content-collector
"""
