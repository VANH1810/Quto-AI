"""Cứu hộ (SOS) — giống app bản đồ cứu hộ bão Yagi.

Luồng: người gặp nạn gửi toạ độ + tình huống (SosCreate) → lưu vào DB, hiện trên
dashboard admin (RescueRequest) → BE cử ĐỘI CỨU HỘ gần nhất (assign) → cập nhật
trạng thái tới khi 'resolved'.
"""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field


class DangerType(str, Enum):
    flood_trapped = "flood_trapped"      # mắc kẹt trong lũ
    landslide_buried = "landslide_buried"  # bị vùi lấp sạt lở
    injured = "injured"                  # bị thương cần y tế
    isolated = "isolated"                # bị cô lập (mất đường/mất liên lạc)
    missing = "missing"                  # mất tích
    other = "other"


class RescueStatus(str, Enum):
    pending = "pending"            # mới nhận, chờ điều phối
    acknowledged = "acknowledged"  # admin đã tiếp nhận
    dispatched = "dispatched"      # đã cử đội cứu hộ
    resolved = "resolved"          # đã cứu/xử lý xong
    cancelled = "cancelled"        # huỷ (báo nhầm/trùng)

class CommuneMappingStatus(str, Enum):
    mapped = "MAPPED"
    unmapped = "UNMAPPED"
    manually_confirmed = "MANUALLY_CONFIRMED"


class TeamStatus(str, Enum):
    available = "available"
    busy = "busy"


# Mức ưu tiên suy ra từ loại nguy hiểm.
_PRIORITY = {
    DangerType.landslide_buried: "critical",
    DangerType.missing: "critical",
    DangerType.injured: "critical",
    DangerType.flood_trapped: "high",
    DangerType.isolated: "medium",
    DangerType.other: "medium",
}


def priority_of(danger: DangerType) -> str:
    return _PRIORITY.get(danger, "medium")


# ---- SOS request ----
class SosCreate(BaseModel):
    """Người gặp nạn gửi (từ app dân / web). Toạ độ bắt buộc; danh tính tuỳ chọn."""

    lat: float = Field(..., ge=-90, le=90, examples=[21.531])
    lon: float = Field(..., ge=-180, le=180, examples=[103.081])
    danger_type: DangerType = DangerType.flood_trapped
    num_people: int = Field(1, ge=1, description="Số người đang gặp nạn")
    full_name: str | None = None
    phone: str | None = None
    cccd: str | None = Field(None, description="Nếu có: tự điền tên/SĐT/xã từ DB công dân")
    note: str | None = Field(None, description="Mô tả thêm, vd 'kẹt trên mái nhà 3 người'")
    commune_code: str | None = Field(None, description="Bỏ trống → tự suy từ toạ độ")


class RescueRequest(BaseModel):
    id: str
    lat: float
    lon: float
    danger_type: DangerType
    num_people: int
    full_name: str | None = None
    phone: str | None = None
    cccd: str | None = None
    note: str | None = None
    commune_code: str | None = None
    commune_name: str | None = None
    mapping_status: CommuneMappingStatus = CommuneMappingStatus.unmapped
    priority: str
    status: RescueStatus
    assigned_team_id: str | None = None
    assigned_team_name: str | None = None
    distance_km: float | None = None
    eta_min: int | None = None
    nearest_shelter_name: str | None = None
    created_at: str
    updated_at: str
    audit: list[dict] = Field(default_factory=list)


class RescueStatusUpdate(BaseModel):
    status: RescueStatus
    note: str | None = None


# ---- Rescue team ----
class RescueTeamCreate(BaseModel):
    name: str
    commune_code: str
    base_lat: float
    base_lon: float
    phone: str | None = None
    capacity: int = Field(6, description="Số người đội có thể ứng cứu 1 lượt")


class RescueTeam(RescueTeamCreate):
    id: str
    status: TeamStatus = TeamStatus.available
    current_request_id: str | None = None
