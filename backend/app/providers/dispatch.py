"""Gửi bản tin đa kênh: Zalo ZNS, SMS brandname, loa IP.

Provider mock: mô phỏng kết quả TẤT ĐỊNH (theo tên xã) — hầu hết thành công,
loa 'Huổi Chan' cố tình fail để minh hoạ luồng gửi-lại / đến-tận-nhà.
Provider live: chỗ để cắm eSMS/VietGuys, Zalo OA/ZNS, API loa (Việt Hưng/VNPT/Viettel).
"""

from __future__ import annotations

from app.config import get_settings
from app.schemas.alert import DispatchRecord, DispatchStatus
from app.schemas.common import Channel

# Loa cố tình 'ngoại tuyến' để demo retry/home-visit (khớp ảnh dashboard).
_OFFLINE_SPEAKERS = {"muong_pon"}  # xã có 1 cụm loa mất kết nối


async def send(channel: Channel, commune_code: str, target: str,
               recipients: int, text: str) -> DispatchRecord:
    settings = get_settings()
    if settings.dispatch_provider.lower() == "live":  # pragma: no cover
        return await _live(channel, commune_code, target, recipients, text)

    # ---- Mock (tất định) ----
    if channel == Channel.loudspeaker and commune_code in _OFFLINE_SPEAKERS:
        return DispatchRecord(
            channel=channel.value, target=target, recipients=recipients, delivered=0,
            status=DispatchStatus.failed,
            detail="1 cụm loa ngoại tuyến (mất kết nối 3G/4G) — cần thử lại hoặc đến bản.",
        )
    # SMS/ZNS: giả lập rớt ~5% (tất định theo số lượng).
    delivered = recipients if channel == Channel.loudspeaker else max(0, recipients - recipients // 20)
    status = DispatchStatus.ok if delivered == recipients else DispatchStatus.ok
    return DispatchRecord(
        channel=channel.value, target=target, recipients=recipients,
        delivered=delivered, status=status,
        detail="Đã phát loa" if channel == Channel.loudspeaker else f"Đã gửi {delivered}/{recipients}",
    )


async def _live(channel: Channel, commune_code: str, target: str,
                recipients: int, text: str) -> DispatchRecord:  # pragma: no cover
    raise RuntimeError(
        "DISPATCH_PROVIDER=live chưa cấu hình gateway. Cắm eSMS/Zalo ZNS/loa IP tại đây."
    )
