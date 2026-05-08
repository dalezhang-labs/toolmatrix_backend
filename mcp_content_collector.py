"""MCP server exposing content_collector queries to Hermes / Claude / Kiro.

Runs as a standalone stdio process. Talks to the deployed FastAPI backend via
HTTP — no direct DB access needed, so the server can run from any machine that
can reach the Railway URL.

Install Dale's end (one-time):
    pip install "mcp>=1.0,<2.0" httpx

Wire it into `~/.kiro/settings/mcp.json`:

    "content-collector": {
      "command": "python3",
      "args": ["/Users/dizhang/Projects/side-projects/toolmatrix_backend/mcp_content_collector.py"],
      "env": {
        "CONTENT_COLLECTOR_API": "https://positive-warmth-production.up.railway.app"
      },
      "disabled": false,
      "autoApprove": ["list_hot_items", "list_events", "list_topics", "get_topic", "get_event"]
    }
"""

from __future__ import annotations

import asyncio
import os
from typing import Any

import httpx
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import TextContent, Tool

API = os.getenv(
    "CONTENT_COLLECTOR_API",
    "https://positive-warmth-production.up.railway.app",
).rstrip("/")


app = Server("content-collector")


async def _get(path: str, params: dict | None = None) -> dict:
    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.get(f"{API}{path}", params=params or {})
        resp.raise_for_status()
        return resp.json()


@app.list_tools()
async def list_tools() -> list[Tool]:
    return [
        Tool(
            name="list_hot_items",
            description=(
                "List top hot items from the last N days, optionally filtered "
                "by language or source. Use this to answer questions like "
                "'最近一周微博什么最火' or 'show me today's HN top posts'."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "days": {"type": "integer", "minimum": 1, "maximum": 14, "default": 7},
                    "lang": {"type": "string", "enum": ["zh", "en"], "description": "optional"},
                    "source": {"type": "string", "description": "source slug, e.g. 'weibo'"},
                    "sort": {
                        "type": "string",
                        "enum": ["ranked", "latest", "hot"],
                        "default": "ranked",
                    },
                    "limit": {"type": "integer", "minimum": 1, "maximum": 100, "default": 20},
                },
            },
        ),
        Tool(
            name="list_events",
            description=(
                "List influential events (stories with ≥3 sources + high heat "
                "in the last 24h). Returns deduplicated events. Use for "
                "questions like '最近有什么大事件'."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "active_only": {"type": "boolean", "default": True},
                    "lang": {"type": "string", "enum": ["zh", "en"]},
                    "limit": {"type": "integer", "minimum": 1, "maximum": 50, "default": 20},
                },
            },
        ),
        Tool(
            name="get_event",
            description="Get one event with its member items (sources that reported it).",
            inputSchema={
                "type": "object",
                "properties": {"event_id": {"type": "integer"}},
                "required": ["event_id"],
            },
        ),
        Tool(
            name="list_topics",
            description=(
                "List trending topics (clusters of related items across sources). "
                "Use for 'what topics are trending' questions."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "lang": {"type": "string", "enum": ["zh", "en"]},
                    "limit": {"type": "integer", "minimum": 1, "maximum": 50, "default": 20},
                },
            },
        ),
        Tool(
            name="get_topic",
            description="Get one topic with its member items.",
            inputSchema={
                "type": "object",
                "properties": {"topic_id": {"type": "integer"}},
                "required": ["topic_id"],
            },
        ),
        Tool(
            name="list_sources",
            description="List all configured sources with health status (last success, errors).",
            inputSchema={"type": "object", "properties": {}},
        ),
    ]


def _format_items(items: list[dict]) -> str:
    """Compact text list that fits in a single Hermes reply."""
    lines = []
    for i, it in enumerate(items, 1):
        src = (it.get("source") or {}).get("name", "?")
        hot = it.get("hot_raw")
        hot_s = f"🔥{int(hot):,} " if isinstance(hot, (int, float)) else ""
        lines.append(f"{i}. [{src}] {hot_s}{it.get('title','')}\n   {it.get('url','')}")
    return "\n".join(lines)


@app.call_tool()
async def call_tool(name: str, arguments: dict[str, Any]) -> list[TextContent]:
    if name == "list_hot_items":
        data = await _get("/api/content-collector/items", arguments)
        text = (
            f"Window: last {data.get('window_days')} day(s), "
            f"{data.get('total')} items\n\n"
            + _format_items(data.get("items") or [])
        )
        return [TextContent(type="text", text=text)]

    if name == "list_events":
        data = await _get("/api/content-collector/topics/events/list", arguments)
        events = data.get("events") or []
        lines = [f"{len(events)} events:"]
        for e in events:
            lines.append(
                f"#{e['id']} [{e['source_count']} 源, {e['item_count']} 条, "
                f"peak {e['peak_score']:.0f}] {e['label']}"
                + (f"  ({', '.join(e.get('keywords', [])[1:4])})" if len(e.get("keywords") or []) > 1 else "")
            )
        return [TextContent(type="text", text="\n".join(lines))]

    if name == "get_event":
        eid = int(arguments["event_id"])
        data = await _get(f"/api/content-collector/topics/events/{eid}")
        e = data.get("event") or {}
        out = [
            f"Event #{e.get('id')}: {e.get('label')}",
            f"Keywords: {', '.join(e.get('keywords') or [])}",
            f"{e.get('source_count')} sources · {e.get('item_count')} items · peak {e.get('peak_score', 0):.0f}",
            "",
            _format_items(data.get("items") or []),
        ]
        return [TextContent(type="text", text="\n".join(out))]

    if name == "list_topics":
        data = await _get("/api/content-collector/topics", arguments)
        topics = data.get("topics") or []
        lines = [f"{len(topics)} topics:"]
        for t in topics:
            lines.append(
                f"#{t['id']} [{t['source_diversity']} 源, score {t['total_score']:.0f}] "
                f"{t['label']}"
            )
        return [TextContent(type="text", text="\n".join(lines))]

    if name == "get_topic":
        tid = int(arguments["topic_id"])
        data = await _get(f"/api/content-collector/topics/{tid}")
        t = data.get("topic") or {}
        out = [
            f"Topic #{t.get('id')}: {t.get('label')}",
            f"Keywords: {', '.join(t.get('keywords') or [])}",
            "",
            _format_items(data.get("items") or []),
        ]
        return [TextContent(type="text", text="\n".join(out))]

    if name == "list_sources":
        data = await _get("/api/content-collector/sources")
        lines = [f"{data.get('total')} sources:"]
        for s in data.get("sources") or []:
            status = "ERR" if s.get("last_error") else "OK"
            lines.append(
                f"  [{status}] {s['slug']:20s} {s['name']}  "
                f"(every {s['interval_sec']}s, weight {s['weight']:.2f})"
            )
        return [TextContent(type="text", text="\n".join(lines))]

    return [TextContent(type="text", text=f"unknown tool: {name}")]


async def main() -> None:
    async with stdio_server() as (read, write):
        await app.run(read, write, app.create_initialization_options())


if __name__ == "__main__":
    asyncio.run(main())
