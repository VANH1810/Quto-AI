"""Nhật ký tương tác — mọi lần GỬI tin (Zalo/SMS/loa) đều ghi 1 dòng.

Khớp bảng 'Nhật ký gửi tin' trên dashboard. Dữ liệu đến từ 2 nguồn:
  1. Phát loa (module loudspeakers) → ghi trực tiếp.
  2. Tổng hợp từ DB3 tin nhắn cá nhân (gộp theo cảnh báo + kênh) → số THẬT.
"""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field

from app.schemas.common import Channel


class SendStatus(str, Enum):
    ok = "ok"            # tất cả đã nhận
    partial = "partial"  # một phần lỗi
    failed = "failed"    # lỗi toàn bộ


class InteractionLog(BaseModel):
    id: str
    ts: str = Field(..., description="Thời điểm gửi")
    channel: str = Field(..., description="zalo_zns | sms | loudspeaker")
    target: str = Field(..., description="Nơi/nhóm nhận, vd 'công dân xã Mường Pồn' hoặc 'Loa bản Lĩnh'")
    commune_code: str | None = None
    lang: str | None = None
    recipients: int = 0
    delivered: int = 0
    status: SendStatus
    detail: str = ""
    alert_id: str | None = None
    ref_id: str | None = Field(None, description="id loa / broadcast liên quan")
    source: str = Field("log", description="log (ghi trực tiếp) | aggregated (gộp từ tin nhắn)")


class InteractionCreate(BaseModel):
    channel: Channel
    target: str
    commune_code: str | None = None
    lang: str | None = None
    recipients: int = 0
    delivered: int = 0
    status: SendStatus = SendStatus.ok
    detail: str = ""
    alert_id: str | None = None
    ref_id: str | None = None
