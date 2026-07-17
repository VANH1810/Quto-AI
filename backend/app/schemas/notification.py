"""DB3 — Tin nhắn cảnh báo gửi tới TỪNG người dân (nhật ký gửi cấp cá nhân).

Mỗi bản ghi = 1 cảnh báo tới 1 công dân: kênh, ngôn ngữ, trạng thái, ĐỊA CHỈ nhà,
và NƠI TRÚ ẨN an toàn gần nhất (để cán bộ đến tận nhà / hướng dẫn sơ tán khi lỗi).
"""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field


class NotificationStatus(str, Enum):
    sent = "sent"              # đã gửi thành công (Zalo/SMS/loa)
    failed = "failed"          # gửi lỗi → cần gửi lại / đến tận nhà
    home_visit = "home_visit"  # cán bộ đã đến tận nhà báo trực tiếp (đã xử lý)


class Notification(BaseModel):
    id: str
    alert_id: str
    cccd: str
    full_name: str
    address: str
    commune_code: str
    channel: str
    lang: str
    status: NotificationStatus
    nearest_shelter_id: str | None = None
    nearest_shelter_name: str | None = None
    nearest_shelter_address: str | None = None
    nearest_shelter_km: float | None = None
    detail: str = ""
    created_at: str = Field(..., description="Thời điểm gửi")


class NotificationUpdate(BaseModel):
    """Cập nhật 1 tin nhắn — dùng khi cán bộ đến tận nhà báo xong (status=home_visit)."""

    status: NotificationStatus
    detail: str | None = None
