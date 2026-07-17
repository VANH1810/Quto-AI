"""Kho cảnh báo + task 'đến tận nhà' (in-memory)."""

from __future__ import annotations

import uuid

from app.schemas.alert import Alert, HomeVisitTask


class AlertStore:
    def __init__(self) -> None:
        self._alerts: dict[str, Alert] = {}
        self._home_visits: dict[str, HomeVisitTask] = {}

    # ---- Alerts ----
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

    # ---- Home-visit tasks ----
    def add_home_visit(self, task: HomeVisitTask) -> HomeVisitTask:
        self._home_visits[task.id] = task
        return task

    def home_visits(self, status: str | None = None) -> list[HomeVisitTask]:
        items = list(self._home_visits.values())
        if status:
            items = [t for t in items if t.status == status]
        return items

    def get_home_visit(self, task_id: str) -> HomeVisitTask | None:
        return self._home_visits.get(task_id)

    @staticmethod
    def new_task_id() -> str:
        return "hv_" + uuid.uuid4().hex[:8]


alerts_store = AlertStore()
