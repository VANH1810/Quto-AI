"""Agent điều phối cảnh báo (mô phỏng vòng đời 1 cảnh báo).

Đây là 'AI-native heart': từ HazardEvent do risk engine phát ra, agent gọi các
'tool' (llm.generate_bulletins, tts.synthesize, dispatch.send) theo trình tự,
có human-in-the-loop khi cấp cao, và ghi audit từng bước (data provenance).

Kiến trúc để lộ các tool này qua MCP sau này rất tự nhiên (mỗi hàm = 1 tool).
"""

from __future__ import annotations

from datetime import datetime

from app.config import get_settings
from app.providers import dispatch as dispatch_provider
from app.providers import llm, tts
from app.schemas.alert import (Alert, AlertStatus, DispatchStatus,
                               HazardEvent, HomeVisitTask)
from app.schemas.common import Channel, Lang
from app.schemas.notification import Notification, NotificationStatus
from app.services.admins import admins
from app.services.alerts import alerts_store
from app.services.citizens import citizens
from app.services.notifications import notifications as notif_store
from app.services.shelters import shelters as shelter_store

# Kênh gửi cho công dân + nhóm cán bộ.
_CITIZEN_CHANNELS = [Channel.zalo_zns, Channel.sms, Channel.loudspeaker]


def _now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


async def create_alert(event: HazardEvent, langs: list[Lang] | None = None) -> Alert:
    """Bước 1–3: sinh bản tin đa ngữ + TTS, quyết định có cần người duyệt.

    - Cấp >= HUMAN_APPROVAL_MIN_LEVEL → status=pending_approval (chờ admin).
    - Thấp hơn → status=approved (agent tự gửi ở bước dispatch).
    """
    settings = get_settings()
    langs = langs or [Lang.vi, Lang.tai, Lang.hmn]

    alert = Alert(
        id=alerts_store.new_id(), event=event, status=AlertStatus.detected,
        created_at=_now(),
    )
    alerts_store.save(alert)
    alerts_store.log(alert.id, "detect",
                     f"{event.hazard} @ {event.commune_name} — {event.risk_label} "
                     f"({event.provenance.rule})")

    # Tool: sinh bản tin (LLM chỉ diễn đạt/dịch)
    bulletins = await llm.generate_bulletins(event, langs)
    # Tool: TTS cho loa (tiếng dân tộc)
    for b in bulletins:
        try:
            b.audio_url = await tts.synthesize(b.body, Lang(b.lang))
        except Exception as e:  # noqa: BLE001
            alerts_store.log(alert.id, "tts_skip", f"{b.lang}: {e}")
    alert.bulletins = bulletins
    alerts_store.log(alert.id, "generate", f"Đã sinh {len(bulletins)} bản tin: "
                     + ", ".join(b.lang for b in bulletins))

    if event.risk_level >= settings.human_approval_min_level:
        alert.status = AlertStatus.pending_approval
        alerts_store.log(alert.id, "human_loop",
                         f"Cấp {event.risk_level} ≥ ngưỡng {settings.human_approval_min_level} "
                         "→ CHỜ người duyệt.")
    else:
        alert.status = AlertStatus.approved
        alerts_store.log(alert.id, "auto", "Cấp thấp → agent tự duyệt, sẵn sàng gửi.")
    alerts_store.save(alert)
    return alert


async def approve_and_dispatch(alert: Alert, admin_id: str,
                               edited_body_vi: str | None = None) -> Alert:
    """Bước human duyệt → gửi. Nếu admin sửa nội dung tiếng Việt thì cập nhật."""
    if edited_body_vi:
        for b in alert.bulletins:
            if b.lang == Lang.vi.value:
                b.body = edited_body_vi
        alerts_store.log(alert.id, "edit", f"{admin_id} sửa nội dung bản tin tiếng Việt.")
    alert.status = AlertStatus.approved
    alert.approved_by = admin_id
    alerts_store.log(alert.id, "approve", f"{admin_id} phê duyệt.")
    return await dispatch(alert)


async def reject(alert: Alert, admin_id: str, note: str | None) -> Alert:
    alert.status = AlertStatus.rejected
    alert.approved_by = admin_id
    alerts_store.log(alert.id, "reject", f"{admin_id} bác bỏ. {note or ''}".strip())
    alerts_store.save(alert)
    return alert


async def dispatch(alert: Alert) -> Alert:
    """Bước 4: gửi đa kênh cho công dân trong xã. Lỗi → tạo task đến-tận-nhà.

    Ngoài nhật ký gửi cấp xã (DispatchRecord), tạo bản ghi tin nhắn cấp CÁ NHÂN
    (Notification) cho từng công dân — kèm địa chỉ + nơi trú ẩn gần nhất.
    """
    alert.status = AlertStatus.dispatching
    event = alert.event
    body_vi = next((b.body for b in alert.bulletins if b.lang == Lang.vi.value),
                   alert.bulletins[0].body if alert.bulletins else "")

    # Gửi từng kênh (cấp xã) + nhớ trạng thái để suy ra tin nhắn cá nhân.
    ch_status: dict[str, DispatchStatus] = {}
    any_fail = False
    for ch in _CITIZEN_CHANNELS:
        people = citizens.contactable(event.commune_code, ch.value)
        rec = await dispatch_provider.send(ch, event.commune_code,
                                           f"công dân {event.commune_name}", len(people), body_vi)
        alert.dispatches.append(rec)
        ch_status[ch.value] = rec.status
        alerts_store.log(alert.id, "dispatch", f"[{ch.value}] {rec.status.value} — {rec.detail}")
        if rec.status == DispatchStatus.failed:
            any_fail = True
            _escalate_home_visit(alert, rec.detail)

    _record_notifications(alert, ch_status)

    alert.status = AlertStatus.partial_failed if any_fail else AlertStatus.sent
    alerts_store.save(alert)
    return alert


def _primary_channel(citizen) -> Channel:
    """Kênh chính cho 1 công dân: Zalo nếu có consent+SĐT, không thì loa."""
    if citizen.consent_zalo_sms and citizen.phone:
        return Channel.zalo_zns
    return Channel.loudspeaker


def _record_notifications(alert: Alert, ch_status: dict[str, DispatchStatus]) -> None:
    """Tạo Notification cho từng công dân trong xã, gắn nơi trú ẩn gần nhà nhất."""
    event = alert.event
    created: list[Notification] = []
    for c in citizens.by_commune(event.commune_code):
        ch = _primary_channel(c)
        st = ch_status.get(ch.value, DispatchStatus.ok)
        status = NotificationStatus.sent if st == DispatchStatus.ok else NotificationStatus.failed
        shelter = shelter_store.nearest(event.commune_code, c.lat, c.lon)
        n = notif_store.add(Notification(
            id=notif_store.new_id(), alert_id=alert.id, cccd=c.cccd, full_name=c.full_name,
            address=c.address, commune_code=c.commune_code, channel=ch.value,
            lang=c.preferred_lang.value, status=status,
            nearest_shelter_id=shelter.id if shelter else None,
            nearest_shelter_name=shelter.name if shelter else None,
            nearest_shelter_address=shelter.address if shelter else None,
            nearest_shelter_km=shelter.distance_km if shelter else None,
            detail=f"Bản tin {c.preferred_lang.value} qua {ch.value}",
            created_at=_now(),
        ))
        created.append(n)
    alerts_store.log(alert.id, "notify",
                     f"Ghi {len(created)} tin nhắn cá nhân (kèm nơi trú ẩn gần nhất).")
    _mirror_notifications(alert.id, created)


def _mirror_notifications(alert_id: str, created: list[Notification]) -> None:
    """Đẩy tin nhắn lên Supabase nếu đang bật (không chặn luồng khi lỗi)."""
    try:
        from app.services import supabase_repo
        if supabase_repo.enabled() and created:
            supabase_repo.push_notifications(created)
    except Exception as e:  # noqa: BLE001
        alerts_store.log(alert_id, "mirror_skip", f"Supabase: {e}")


async def retry_failed(alert: Alert) -> Alert:
    """Gửi lại các kênh đang failed. Vẫn lỗi → giữ/nhắc task đến-tận-nhà."""
    event = alert.event
    body_vi = next((b.body for b in alert.bulletins if b.lang == Lang.vi.value), "")
    still_fail = False
    for rec in alert.dispatches:
        if rec.status != DispatchStatus.failed:
            continue
        ch = Channel(rec.channel)
        rec.status = DispatchStatus.retrying
        new = await dispatch_provider.send(ch, event.commune_code, rec.target,
                                           rec.recipients, body_vi)
        rec.status, rec.delivered, rec.detail = new.status, new.delivered, new.detail
        alerts_store.log(alert.id, "retry", f"[{ch.value}] → {rec.status.value}: {rec.detail}")
        if rec.status == DispatchStatus.failed:
            still_fail = True

    # Cập nhật trạng thái tin nhắn cá nhân theo kết quả gửi lại.
    ch_status = {d.channel: d.status for d in alert.dispatches}
    for n in notif_store.by_alert(alert.id):
        st = ch_status.get(n.channel, DispatchStatus.ok)
        n.status = NotificationStatus.sent if st == DispatchStatus.ok else NotificationStatus.failed

    alert.status = AlertStatus.partial_failed if still_fail else AlertStatus.sent
    alerts_store.save(alert)
    return alert


def _escalate_home_visit(alert: Alert, reason: str) -> None:
    """Tạo task 'đến tận nhà báo' giao cho cán bộ phụ trách xã."""
    assignees = admins.for_commune(alert.event.commune_code)
    assigned = assignees[0].id if assignees else None
    task = HomeVisitTask(
        id=alerts_store.new_task_id(), alert_id=alert.id,
        commune_code=alert.event.commune_code, assigned_admin_id=assigned,
        reason=f"Gửi lỗi: {reason}", created_at=_now(),
    )
    alerts_store.add_home_visit(task)
    alerts_store.log(alert.id, "home_visit",
                     f"Tạo task đến-tận-nhà {task.id} → cán bộ {assigned or '(chưa có)'}.")
