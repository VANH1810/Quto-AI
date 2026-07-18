"""Sự kiện thiên tai (hazard event) + bản tin đa ngữ + nhật ký gửi.

Vendor từ backend/app/schemas/alert.py (agent_worker chỉ dùng một phần: HazardEvent,
Provenance, BulletinText, DispatchRecord, DispatchStatus).
"""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field


class DispatchStatus(str, Enum):
    ok = "ok"
    failed = "failed"
    retrying = "retrying"
    home_visit = "home_visit"


class Provenance(BaseModel):
    """Dòng truy vết nguồn dữ liệu — in kèm mọi bản tin."""

    source: str
    rule: str = Field(..., description="Quy tắc QĐ18 kích hoạt")
    triggered_by: dict = Field(default_factory=dict, description="Số liệu cụ thể đã vượt ngưỡng")
    observed_at: str


class BulletinText(BaseModel):
    lang: str
    title: str
    body: str
    audio_url: str | None = None


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
    target: str = Field(..., description="Nhóm/định danh người nhận")
    recipients: int = 0
    delivered: int = 0
    status: DispatchStatus
    detail: str = ""
