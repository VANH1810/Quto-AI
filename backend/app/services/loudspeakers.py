"""Kho loa truyền thanh (in-memory) — tự sinh 1 loa/xã + phát bản tin.

Mường Pồn có thêm 1 loa bản 'Huổi Chan' ĐỂ OFFLINE minh hoạ luồng thử lại (khớp
ảnh dashboard). Phát loa → ghi vào nhật ký tương tác.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from app.schemas.common import Channel
from app.schemas.interaction import InteractionCreate, SendStatus
from app.schemas.loudspeaker import (BroadcastRequest, BroadcastResult,
                                     Loudspeaker, LoudspeakerCreate,
                                     SpeakerResult, SpeakerStatus)
from app.services import supabase_repo
from app.services.geo_data import all_communes, short_name


def _now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


class LoudspeakerStore:
    def __init__(self) -> None:
        self._by_id: dict[str, Loudspeaker] = {}
        for c in all_communes():
            self._add(LoudspeakerCreate(
                name=f"Loa trung tâm {short_name(c.name)}", commune_code=c.code,
                location=f"Trung tâm {c.name}", lat=c.lat, lon=c.lon, langs=["vi"]))
        # 1 loa bản offline để minh hoạ thử lại
        s = self._add(LoudspeakerCreate(
            name="Loa bản Huổi Chan", commune_code="muong_pon",
            location="Bản Huổi Chan, Xã Mường Pồn", lat=21.528, lon=103.079,
            langs=["vi", "tai"]))
        s.status = SpeakerStatus.offline

    def _add(self, data: LoudspeakerCreate) -> Loudspeaker:
        sid = "spk_" + uuid.uuid4().hex[:8]
        spk = Loudspeaker(id=sid, status=SpeakerStatus.online, last_seen=_now(), **data.model_dump())
        self._by_id[sid] = spk
        return spk

    # ---- Truy vấn ----
    def all(self, commune_code: str | None = None,
            status: str | None = None) -> list[Loudspeaker]:
        items = list(self._by_id.values())
        if commune_code:
            items = [s for s in items if s.commune_code == commune_code]
        if status:
            items = [s for s in items if s.status.value == status]
        return items

    def get(self, sid: str) -> Loudspeaker | None:
        return self._by_id.get(sid)

    def status_summary(self, communes: set[str] | None = None) -> dict:
        items = [s for s in self._by_id.values() if communes is None or s.commune_code in communes]
        online = sum(1 for s in items if s.status == SpeakerStatus.online)
        return {"total": len(items), "online": online, "offline": len(items) - online}

    def set_status(self, sid: str, status: SpeakerStatus) -> Loudspeaker | None:
        s = self._by_id.get(sid)
        if s is None:
            return None
        s.status = status
        s.last_seen = _now()
        supabase_repo.mirror(supabase_repo.push_loudspeakers, [s])
        return s

    def create(self, data: LoudspeakerCreate) -> Loudspeaker:
        spk = self._add(data)
        supabase_repo.mirror(supabase_repo.push_loudspeakers, [spk])
        return spk

    # ---- Phát bản tin ----
    def broadcast(self, req: BroadcastRequest) -> BroadcastResult:
        from app.services.interactions import interactions

        if req.speaker_ids:
            targets = [self._by_id[i] for i in req.speaker_ids if i in self._by_id]
        elif req.commune_code:
            targets = self.all(commune_code=req.commune_code)
        else:
            targets = []

        results, itx_ids, delivered = [], [], 0
        for s in targets:
            ok = s.status == SpeakerStatus.online
            delivered += ok
            detail = "Đã phát" if ok else "Loa ngoại tuyến — cần thử lại"
            results.append(SpeakerResult(speaker_id=s.id, name=s.name, delivered=ok, detail=detail))
            # Mỗi loa = 1 dòng nhật ký (khớp dashboard: "Loa bản X — phát tiếng Thái")
            itx = interactions.record(InteractionCreate(
                channel=Channel.loudspeaker, target=s.name, commune_code=s.commune_code,
                lang=req.lang, recipients=1, delivered=1 if ok else 0,
                status=SendStatus.ok if ok else SendStatus.failed,
                detail=f"{'phát' if ok else 'ngoại tuyến'} tiếng {req.lang}", ref_id=s.id))
            itx_ids.append(itx.id)

        return BroadcastResult(
            broadcast_id="bcast_" + uuid.uuid4().hex[:8], lang=req.lang,
            requested=len(targets), delivered=delivered, failed=len(targets) - delivered,
            results=results, interaction_ids=itx_ids)


loudspeakers = LoudspeakerStore()
