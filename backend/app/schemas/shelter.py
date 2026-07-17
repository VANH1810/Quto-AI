"""Nơi trú ẩn an toàn (điểm sơ tán) theo xã — có địa chỉ + toạ độ để chỉ đường."""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field


class ShelterKind(str, Enum):
    school = "school"                  # trường học
    community_hall = "community_hall"  # nhà văn hoá/sinh hoạt cộng đồng
    commune_office = "commune_office"  # trụ sở UBND xã
    health_station = "health_station"  # trạm y tế
    high_ground = "high_ground"        # điểm cao an toàn


class ShelterBase(BaseModel):
    commune_code: str
    name: str
    address: str
    lat: float
    lon: float
    capacity: int = Field(0, description="Sức chứa (người)")
    kind: ShelterKind = ShelterKind.community_hall
    contact_phone: str | None = None


class ShelterCreate(ShelterBase):
    pass


class Shelter(ShelterBase):
    id: str
    distance_km: float | None = Field(None, description="Khoảng cách tới điểm truy vấn (nếu có)")
