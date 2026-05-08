"""Fetcher registry: auto-discovers every BaseFetcher subclass under fetchers/.

Usage:
    from .registry import get_registry
    fetcher = get_registry()["hackernews"]
    items = await fetcher.fetch()
"""

from __future__ import annotations

import importlib
import inspect
import logging
import pkgutil
from typing import Type

from .base import BaseFetcher

logger = logging.getLogger(__name__)

_registry: dict[str, BaseFetcher] = {}
_loaded = False


def _discover() -> None:
    """Walk all submodules under fetchers/ and collect BaseFetcher subclasses."""
    global _loaded
    if _loaded:
        return
    package = importlib.import_module(
        "backend.tools.content_collector.fetchers"
    )

    for module_info in pkgutil.walk_packages(
        package.__path__, prefix=package.__name__ + "."
    ):
        if module_info.name.endswith((".base", ".http", ".registry", ".helpers")):
            continue
        try:
            module = importlib.import_module(module_info.name)
        except Exception:  # pragma: no cover — surface failures but keep loading
            logger.exception("Failed to import fetcher module %s", module_info.name)
            continue

        for _, obj in inspect.getmembers(module, inspect.isclass):
            if (
                issubclass(obj, BaseFetcher)
                and obj is not BaseFetcher
                and obj.slug
            ):
                if obj.slug in _registry:
                    # same slug declared twice — last one wins, but log it
                    logger.warning(
                        "Duplicate fetcher slug %r (overwriting %s with %s)",
                        obj.slug,
                        type(_registry[obj.slug]).__module__,
                        obj.__module__,
                    )
                _registry[obj.slug] = obj()

    _loaded = True
    logger.info(
        "content_collector: loaded %d fetchers: %s",
        len(_registry),
        sorted(_registry.keys()),
    )


def get_registry() -> dict[str, BaseFetcher]:
    _discover()
    return _registry


def get_fetcher(slug: str) -> BaseFetcher | None:
    return get_registry().get(slug)


def all_metadata() -> list[dict]:
    """Return metadata rows used to seed the `sources` table."""
    out = []
    for slug, f in get_registry().items():
        out.append(
            {
                "slug": slug,
                "name": f.name,
                "lang": f.lang,
                "category": f.category,
                "region": f.region,
                "fetcher_type": f.fetcher_type,
                "fetcher_config": f.fetcher_config or {},
                "interval_sec": f.interval_sec,
                "weight": f.weight,
                "home_url": f.home_url,
            }
        )
    return sorted(out, key=lambda r: r["slug"])
