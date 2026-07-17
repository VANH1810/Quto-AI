"""Kho cảnh báo (in-memory)."""

from __future__ import annotations

import uuid

from app.schemas.alert import Alert


class AlertStore:
    def __init__(self) -> None:
        self._alerts: dict[str, Alert] = {}

    def save(self, alert: Alert) -> Alert:
        self._alerts[alert.id] = alert
        return alert

    def get(self, alert_id: str) -> Alert | None:
        return self._alerts.get(alert_id)

    def all(self) -> list[Alert]:
        return sorted(self._alerts.values(), key=lambda a: a.created_at, reverse=True)

    def log(self, alert_id: str, step: str, detail: str) -> None:
        a = self._alerts.get(alert_id)
        if a is not None:
            a.audit.append({"step": step, "detail": detail})

    @staticmethod
    def new_id() -> str:
        return "alt_" + uuid.uuid4().hex[:10]


alerts_store = AlertStore()
