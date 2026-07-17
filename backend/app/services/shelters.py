"""Nơi trú ẩn an toàn theo xã (in-memory) — SINH TỰ ĐỘNG từ danh mục 45 xã.

Mỗi xã có sẵn 2 điểm (trường học + nhà văn hoá); xã nhạy cảm sạt lở cao có thêm
1 'điểm cao'. Toạ độ lệch nhẹ quanh tâm xã để `nearest()` (haversine) có ý nghĩa.
Sản phẩm thật thay bằng phương án sơ tán chính thức của từng xã.
"""

from __future__ import annotations

import uuid

from app.schemas.shelter import Shelter, ShelterCreate, ShelterKind
from app.services import supabase_repo
from app.services.geo_data import all_communes, haversine_km, short_name


def _seed_for(commune) -> list[ShelterCreate]:
    s = short_name(commune.name)
    cap = max(120, min(600, commune.population // 12))
    items = [
        ShelterCreate(commune_code=commune.code, name=f"Trường PTDTBT {s}",
                      address=f"Trung tâm {commune.name}", lat=commune.lat, lon=commune.lon,
                      capacity=cap, kind=ShelterKind.school),
        ShelterCreate(commune_code=commune.code, name=f"Nhà văn hoá {s}",
                      address=f"Khu trung tâm, {commune.name}",
                      lat=round(commune.lat + 0.006, 6), lon=round(commune.lon + 0.004, 6),
                      capacity=max(80, cap // 2), kind=ShelterKind.community_hall),
    ]
    if commune.landslide_susceptibility == "high":
        items.append(ShelterCreate(
            commune_code=commune.code, name=f"Điểm cao an toàn {s}",
            address=f"Khu đồi cao, {commune.name}",
            lat=round(commune.lat - 0.005, 6), lon=round(commune.lon + 0.007, 6),
            capacity=200, kind=ShelterKind.high_ground))
    return items


class ShelterStore:
    def __init__(self) -> None:
        self._by_id: dict[str, Shelter] = {}
        for commune in all_communes():
            for data in _seed_for(commune):
                self._add(data)

    def _add(self, data: ShelterCreate) -> Shelter:
        sid = "shl_" + uuid.uuid4().hex[:8]
        shelter = Shelter(id=sid, **data.model_dump())
        self._by_id[sid] = shelter
        return shelter

    def create(self, data: ShelterCreate) -> Shelter:
        shelter = self._add(data)
        supabase_repo.mirror(supabase_repo.push_shelters, [shelter])  # tự đẩy lên Supabase nếu bật
        return shelter

    def all(self) -> list[Shelter]:
        return list(self._by_id.values())

    def by_commune(self, commune_code: str) -> list[Shelter]:
        return [s for s in self._by_id.values() if s.commune_code == commune_code]

    def nearest(self, commune_code: str, lat: float | None, lon: float | None) -> Shelter | None:
        """Điểm trú ẩn gần nhất trong xã. Không có toạ độ → trả điểm đầu tiên của xã."""
        candidates = self.by_commune(commune_code)
        if not candidates:
            return None
        if lat is None or lon is None:
            return candidates[0]
        best = min(candidates, key=lambda s: haversine_km(lat, lon, s.lat, s.lon))
        best = best.model_copy()
        best.distance_km = haversine_km(lat, lon, best.lat, best.lon)
        return best


shelters = ShelterStore()
