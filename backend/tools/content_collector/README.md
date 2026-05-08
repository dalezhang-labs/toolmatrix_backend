# Content Collector

Cross-source 7-day hot board. Part of the toolmatrix shared FastAPI backend.

## Scope (MVP)

- 采集：每个信源一个 fetcher 文件，自动注册，按各自 interval 定时抓取
- 存储：Neon `content_collector` schema，四类表 sources / items / item_snapshots / topics (+events 留空)
- 打分：按源批次 log1p min-max 归一化到 0-100，乘上 source.weight
- 前端：Next.js on Vercel（代码在 `~/self-project/content-collector-web`）

## Current sources (3, smoke-tested)

| slug              | lang | 说明                |
| ----------------- | ---- | ------------------- |
| hackernews        | en   | HN 首页 (30 条)     |
| github_trending   | en   | GitHub Trending 日榜 |
| weibo             | zh   | 微博热搜 (50 条)    |

## Add a new source

1. Create `fetchers/{lang}/mysource.py` with a `BaseFetcher` subclass.
2. Set class attrs: `slug`, `name`, `lang`, `category`, `region`, `interval_sec`, `weight`, `home_url`.
3. Implement `async def fetch() -> list[NewsItem]`.
4. Restart the backend — the registry auto-discovers it, the `sources` table row is created on the first fetch.

## Run locally

From `toolmatrix_backend/`:

```bash
python3 -m uvicorn backend.main:app --reload
```

Then:
```
GET  http://localhost:8000/api/content-collector/sources
POST http://localhost:8000/api/content-collector/admin/fetch/all
GET  http://localhost:8000/api/content-collector/items?days=7&limit=50
```

## Env vars (all optional except DATABASE_URL)

See root `.env.example` → "Tool: Content Collector" section.

## Roadmap (not implemented yet)

- [ ] Remaining 12 sources (zhihu, bilibili, douyin, 36kr, baidu, v2ex, sspai, ithome, reddit, producthunt, lobsters, arxiv)
- [ ] Topic clustering (embedding → 7-day topic rollup)
- [ ] Event detection (≥3 sources within 24h)
- [ ] Retention GC job
- [ ] Auth on admin endpoints
