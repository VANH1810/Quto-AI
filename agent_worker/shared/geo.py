"""Đơn vị hành chính (xã/cụm) Điện Biên + toạ độ. Vendor từ backend/app/schemas/geo.py."""

from __future__ import annotations

from pydantic import BaseModel, Field


class Commune(BaseModel):
    code: str = Field(..., description="Mã xã, vd 'muong_pon'")
    name: str = Field(..., description="Tên xã, vd 'Xã Mường Pồn'")
    district: str = Field(..., description="Huyện")
    lat: float
    lon: float
    elevation_m: float = Field(..., description="Độ cao trung bình (m)")
    landslide_susceptibility: str = "medium"   # low | medium | high
    population: int = 0
