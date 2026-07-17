"""DB3 — Kho tin nhắn cảnh báo gửi tới từng người dân (in-memory)."""

from __future__ import annotations

import uuid

from app.schemas.notification import Notification


class NotificationStore:
    def __init__(self) -> None:
        self._by_id: dict[str, Notification] = {}

    def add(self, n: Notification) -> Notification:
        self._by_id[n.id] = n
        return n

    def all(self) -> list[Notification]:
        return sorted(self._by_id.values(), key=lambda n: n.created_at, reverse=True)

    def by_alert(self, alert_id: str) -> list[Notification]:
        return [n for n in self._by_id.values() if n.alert_id == alert_id]

    def by_citizen(self, cccd: str) -> list[Notification]:
        return [n for n in self._by_id.values() if n.cccd == cccd]

    def get(self, notif_id: str) -> Notification | None:
        return self._by_id.get(notif_id)

    @staticmethod
    def new_id() -> str:
        return "ntf_" + uuid.uuid4().hex[:10]


notifications = NotificationStore()
