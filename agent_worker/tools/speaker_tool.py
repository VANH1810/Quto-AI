"""Tool phát loa công cộng (loudspeaker) — mock tất định cho demo.

Kênh cá nhân (Telegram) nằm ở telegram_tool.py. File này chỉ còn lo kênh loa:
loa 'muong_pon' cố tình fail để minh hoạ gửi lại / đến tận nhà.
"""

from __future__ import annotations

import logging

from agent_worker.shared.alert import DispatchRecord, DispatchStatus

log = logging.getLogger("agent_worker.speaker")

_OFFLINE_SPEAKERS = {"muong_pon"}          # khớp demo dashboard


async def send(channel: str, commune_code: str, recipient: dict, title: str, body: str,
               template: dict | None = None, attempt: int = 0) -> DispatchRecord:
    """Gửi qua loa (kênh 'loudspeaker'). Giữ chữ ký chung để dispatch gọi không đổi."""
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
    # kênh lạ → mock ok
    return DispatchRecord(channel=channel, target=name, recipients=1, delivered=1,
                          status=DispatchStatus.ok, detail=f"[mock] {channel}")
