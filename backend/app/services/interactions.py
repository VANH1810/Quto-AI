"""Kho nhật ký tương tác (in-memory) + tổng hợp từ tin nhắn cá nhân thật."""

from __future__ import annotations

import uuid
from datetime import datetime

from app.schemas.interaction import (InteractionCreate, InteractionLog,
                                     SendStatus)
from app.services import supabase_repo


def _now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _status(delivered: int, recipients: int) -> SendStatus:
    if recipients == 0 or delivered == 0:
        return SendStatus.failed if recipients else SendStatus.ok
    if delivered >= recipients:
        return SendStatus.ok
    return SendStatus.partial


class InteractionStore:
    def __init__(self) -> None:
        self._by_id: dict[str, InteractionLog] = {}

    def record(self, data: InteractionCreate) -> InteractionLog:
        entry = InteractionLog(
            id="itx_" + uuid.uuid4().hex[:10], ts=_now(),
            channel=data.channel.value, target=data.target, commune_code=data.commune_code,
            lang=data.lang, recipients=data.recipients, delivered=data.delivered,
            status=data.status, detail=data.detail, alert_id=data.alert_id,
            ref_id=data.ref_id, source="log",
        )
        self._by_id[entry.id] = entry
        supabase_repo.mirror(supabase_repo.push_interactions, [entry])
        return entry

    # ---- Tổng hợp từ DB3 tin nhắn cá nhân (số thật) ----
    @staticmethod
    def _aggregated_from_notifications() -> list[InteractionLog]:
        from app.services.notifications import notifications

        groups: dict[tuple, dict] = {}
        for n in notifications.all():
            key = (n.alert_id, n.channel, n.commune_code)
            g = groups.setdefault(key, {"recipients": 0, "delivered": 0, "lang": n.lang,
                                        "ts": n.created_at})
            g["recipients"] += 1
            if n.status.value in ("sent", "home_visit"):
                g["delivered"] += 1
            g["ts"] = max(g["ts"], n.created_at)  # mốc gần nhất

        out = []
        for (alert_id, channel, commune), g in groups.items():
            out.append(InteractionLog(
                id=f"agg_{alert_id}_{channel}_{commune}",
                ts=g["ts"], channel=channel, target=f"công dân xã {commune}",
                commune_code=commune, lang=g["lang"], recipients=g["recipients"],
                delivered=g["delivered"], status=_status(g["delivered"], g["recipients"]),
                detail=f"{g['delivered']}/{g['recipients']} người nhận",
                alert_id=alert_id, source="aggregated",
            ))
        return out

    def list(self, commune_code: str | None = None, channel: str | None = None,
             status: str | None = None, limit: int = 200) -> list[InteractionLog]:
        items = list(self._by_id.values()) + self._aggregated_from_notifications()
        if commune_code:
            items = [i for i in items if i.commune_code == commune_code]
        if channel:
            items = [i for i in items if i.channel == channel]
        if status:
            items = [i for i in items if i.status.value == status]
        items.sort(key=lambda i: i.ts, reverse=True)
        return items[:limit]


interactions = InteractionStore()
