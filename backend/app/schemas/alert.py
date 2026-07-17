"""Sự kiện thiên tai (hazard event) + bản tin đa ngữ + nhật ký gửi.

Luồng: risk engine → HazardEvent → agent sinh Bulletin → (human duyệt nếu cấp cao)
→ dispatch đa kênh → DispatchRecord. Bản tin theo tinh thần CAP (có provenance).
"""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field


class AlertStatus(str, Enum):
    detected = "detected"                  # risk engine vừa phát hiện
    pending_approval = "pending_approval"  # chờ người duyệt (cấp cao)
    approved = "approved"                  # đã duyệt, sẵn sàng gửi
    dispatching = "dispatching"
    sent = "sent"                          # đã gửi (toàn bộ/đa số thành công)
    partial_failed = "partial_failed"      # có kênh/người nhận lỗi
    rejected = "rejected"                  # người duyệt bác bỏ


class DispatchStatus(str, Enum):
    ok = "ok"
    failed = "failed"
    retrying = "retrying"


class Provenance(BaseModel):
    """Dòng truy vết nguồn dữ liệu — in kèm mọi bản tin."""

    source: str
    rule: str = Field(..., description="Quy tắc QĐ18 kích hoạt, vd 'lũ quét QĐ18-LQ mức 3'")
    triggered_by: dict = Field(default_factory=dict, description="Số liệu cụ thể đã vượt ngưỡng")
    observed_at: str


class BulletinText(BaseModel):
    lang: str
    title: str
    body: str
    audio_url: str | None = None  # file TTS (nếu có)


class HazardEvent(BaseModel):
    hazard: str
    commune_code: str
    commune_name: str
    risk_level: int
    risk_color: str
    risk_label: str
    provenance: Provenance
    recommended_actions: list[str] = Field(default_factory=list)


class DispatchRecord(BaseModel):
    channel: str
    target: str = Field(..., description="Nhóm/định danh người nhận, vd 'công dân xã Mường Pồn'")
    recipients: int = 0
    delivered: int = 0
    status: DispatchStatus
    detail: str = ""


class Alert(BaseModel):
    id: str
    event: HazardEvent
    status: AlertStatus
    bulletins: list[BulletinText] = Field(default_factory=list)
    dispatches: list[DispatchRecord] = Field(default_factory=list)
    audit: list[dict] = Field(default_factory=list)
    created_at: str
    approved_by: str | None = None


class ApproveRequest(BaseModel):
    approve: bool = True
    note: str | None = None
    edited_body_vi: str | None = Field(None, description="Người duyệt sửa lại nội dung tiếng Việt (tuỳ chọn)")
