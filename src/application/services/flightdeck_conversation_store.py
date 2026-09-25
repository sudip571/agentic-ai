from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from threading import Lock
from typing import Any


@dataclass
class PendingFlightdeckRequest:
    conversation_id: str
    report_type: str
    params: dict[str, Any]
    missing_fields: list[str]
    updated_at: datetime


class FlightdeckConversationStore:
    def __init__(self, ttl_minutes: int = 30) -> None:
        self._ttl = timedelta(minutes=ttl_minutes)
        self._items: dict[str, PendingFlightdeckRequest] = {}
        self._lock = Lock()

    def get(self, conversation_id: str) -> PendingFlightdeckRequest | None:
        now = datetime.now(UTC)
        with self._lock:
            item = self._items.get(conversation_id)
            if item is None:
                return None
            if now - item.updated_at > self._ttl:
                self._items.pop(conversation_id, None)
                return None
            return item

    def save(self, item: PendingFlightdeckRequest) -> None:
        item.updated_at = datetime.now(UTC)
        with self._lock:
            self._items[item.conversation_id] = item

    def delete(self, conversation_id: str) -> None:
        with self._lock:
            self._items.pop(conversation_id, None)


conversation_store = FlightdeckConversationStore()
