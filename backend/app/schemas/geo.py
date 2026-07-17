"""Đơn vị hành chính (xã/cụm) Điện Biên + toạ độ cho bản đồ."""

from __future__ import annotations

from pydantic import BaseModel, Field


class Commune(BaseModel):
    """Một xã / cụm dân cư có toạ độ + đặc trưng địa hình phục vụ risk engine."""

    code: str = Field(..., description="Mã xã, vd 'muong_pon'")
    name: str = Field(..., description="Tên xã, vd 'Xã Mường Pồn'")
    district: str = Field(..., description="Huyện")
    lat: float
    lon: float
    elevation_m: float = Field(..., description="Độ cao trung bình (m) — dùng cho hiệu chỉnh nhiệt/rét hại")
    # Mức nhạy cảm lũ quét/sạt lở (QĐ18 chia vùng): low | medium | high
    landslide_susceptibility: str = "medium"
    population: int = 0


class CommuneRiskSummary(BaseModel):
    """Tóm tắt hiển thị trên bản đồ / bảng 'Nguy cơ theo xã'."""

    code: str
    name: str
    lat: float
    lon: float
    risk_level: int
    risk_color: str
    risk_label: str
    top_hazard: str | None = None
    top_hazard_label: str | None = None
