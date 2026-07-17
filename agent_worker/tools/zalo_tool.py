"""Tool gọi API Zalo (OA/ZNS) — thật (httpx) + mock tất định cho demo.

ZALO_PROVIDER=mock (mặc định): mô phỏng kết quả theo dữ liệu (loa 'muong_pon' cố tình
fail để minh hoạ gửi lại / đến tận nhà; zalo/sms cần SĐT).
ZALO_PROVIDER=live: gọi Zalo OA thật (cần OA token). SMS/loa cắm gateway riêng ở đây.
"""

from __future__ import annotations

import logging

import httpx

from agent_worker.shared.alert import DispatchRecord, DispatchStatus

from agent_worker.config import get_worker_settings
from agent_worker.infra import cache

log = logging.getLogger("agent_worker.zalo")

_OFFLINE_SPEAKERS = {"muong_pon"}          # khớp demo dashboard
_ZALO_OA_SEND = "https://openapi.zalo.me/v3.0/oa/message"


async def send(channel: str, commune_code: str, recipient: dict, title: str, body: str,
               zalo_template: dict | None = None, attempt: int = 0) -> DispatchRecord:
    settings = get_worker_settings()
    if settings.zalo_provider.lower() == "live" and channel == "zalo_zns":
        return await _live_zns(recipient, zalo_template or {"title": title, "body": body})
    return _mock(channel, commune_code, recipient, body)


def _mock(channel: str, commune_code: str, recipient: dict, body: str) -> DispatchRecord:
    name = recipient.get("full_name", "người dân")
    if channel == "loudspeaker":
        if commune_code in _OFFLINE_SPEAKERS:
            return DispatchRecord(channel=channel, target=name, recipients=1, delivered=0,
                                  status=DispatchStatus.failed,
                                  detail="Cụm loa ngoại tuyến (mất kết nối) — cần thử lại hoặc đến bản.")
        return DispatchRecord(channel=channel, target=name, recipients=1, delivered=1,
                              status=DispatchStatus.ok, detail="Đã phát loa")
    # zalo_zns / sms cần SĐT
    if not recipient.get("phone"):
        return DispatchRecord(channel=channel, target=name, recipients=1, delivered=0,
                              status=DispatchStatus.failed, detail="Không có số điện thoại")
    return DispatchRecord(channel=channel, target=name, recipients=1, delivered=1,
                          status=DispatchStatus.ok, detail=f"Đã gửi {channel} tới {name}")


async def _live_zns(recipient: dict, template_data: dict) -> DispatchRecord:  # pragma: no cover
    name = recipient.get("full_name", "")
    phone = recipient.get("phone")
    if not phone:
        return DispatchRecord(channel="zalo_zns", target=name, recipients=1, delivered=0,
                              status=DispatchStatus.failed, detail="Không có số điện thoại")
    token = await _access_token()
    payload = {"phone": phone, "template_data": template_data}
    async with httpx.AsyncClient(timeout=15) as c:
        r = await c.post(_ZALO_OA_SEND, headers={"access_token": token}, json=payload)
        ok = r.status_code == 200 and (r.json().get("error", 0) == 0)
    return DispatchRecord(
        channel="zalo_zns", target=name, recipients=1, delivered=1 if ok else 0,
        status=DispatchStatus.ok if ok else DispatchStatus.failed,
        detail="Zalo ZNS OK" if ok else f"Zalo lỗi: {r.text[:120]}",
    )


async def send_zns(phone: str, template_id: str, template_data: dict) -> DispatchRecord:  # pragma: no cover
    return await _live_zns({"phone": phone, "full_name": phone},
                           {"template_id": template_id, **template_data})


async def send_oa_message(user_id: str, message: dict) -> DispatchRecord:  # pragma: no cover
    token = await _access_token()
    async with httpx.AsyncClient(timeout=15) as c:
        r = await c.post(_ZALO_OA_SEND, headers={"access_token": token},
                         json={"recipient": {"user_id": user_id}, "message": message})
        ok = r.status_code == 200
    return DispatchRecord(channel="zalo_zns", target=user_id, recipients=1,
                          delivered=1 if ok else 0,
                          status=DispatchStatus.ok if ok else DispatchStatus.failed,
                          detail="OA message OK" if ok else f"OA lỗi: {r.text[:120]}")


async def _access_token() -> str:  # pragma: no cover
    """Lấy/refresh OA access token (cache Redis). Thật: đổi refresh_token định kỳ."""
    tok = await cache.get_zalo_token()
    if tok:
        return tok
    s = get_worker_settings()
    # NOTE: luồng refresh_token thật của Zalo cần lưu refresh_token bền; ở đây rút gọn.
    raise RuntimeError("ZALO_PROVIDER=live: chưa cấu hình OA token/refresh. Cắm tại _access_token().")
