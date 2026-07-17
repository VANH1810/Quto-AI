"""DB3 — Kho tin nhắn cảnh báo gửi tới từng người dân (in-memory)."""

from __future__ import annotations

import uuid

from app.schemas.notification import Notification, NotificationStatus
from app.services import supabase_repo


class NotificationStore:
    def __init__(self) -> None:
        self._by_id: dict[str, Notification] = {}

    def add(self, n: Notification) -> Notification:
        self._by_id[n.id] = n
        return n

    def update(self, notif_id: str, status: NotificationStatus,
               detail: str | None = None) -> Notification | None:
        """Cập nhật trạng thái 1 tin nhắn (vd cán bộ đã đến tận nhà → home_visit)."""
        n = self._by_id.get(notif_id)
        if n is None:
            return None
        n.status = status
        if detail is not None:
            n.detail = detail
        supabase_repo.mirror(supabase_repo.push_notifications, [n])  # đồng bộ Supabase nếu bật
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
