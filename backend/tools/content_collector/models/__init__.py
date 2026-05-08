"""ORM models for content_collector. Importing this package attaches all tables
to the Base.metadata registry so create_all() picks them up."""

from .source import Source
from .item import Item, ItemSnapshot
from .topic import Topic, TopicItem
from .event import Event, EventItem
from .digest import Digest

__all__ = [
    "Source",
    "Item",
    "ItemSnapshot",
    "Topic",
    "TopicItem",
    "Event",
    "EventItem",
    "Digest",
]
