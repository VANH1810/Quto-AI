"""DB — Nơi trú ẩn an toàn theo xã (in-memory + seed).

`nearest()` tìm điểm trú ẩn gần nhất cho 1 toạ độ (haversine) — để gắn vào bản tin
và tin nhắn gửi từng người dân.
"""

from __future__ import annotations

import uuid

from app.schemas.shelter import Shelter, ShelterCreate, ShelterKind
from app.services import supabase_repo
from app.services.geo_data import haversine_km

# Seed điểm trú ẩn mẫu (địa chỉ/toạ độ minh hoạ). Thật: lấy từ phương án sơ tán của xã.
_SEED: list[dict] = [
    dict(commune_code="muong_pon", name="Trường PTDTBT Tiểu học Mường Pồn",
         address="Trung tâm xã Mường Pồn, huyện Điện Biên", lat=21.5335, lon=103.0790,
         capacity=300, kind=ShelterKind.school, contact_phone="0215380xxxx"),
    dict(commune_code="muong_pon", name="Nhà văn hoá bản Nậm Pồn",
         address="Bản Nậm Pồn, xã Mường Pồn", lat=21.5280, lon=103.0835,
         capacity=120, kind=ShelterKind.community_hall, contact_phone=None),
    dict(commune_code="muong_pon", name="Điểm cao UBND xã (khu đồi sau trụ sở)",
         address="UBND xã Mường Pồn", lat=21.5312, lon=103.0808,
         capacity=200, kind=ShelterKind.high_ground, contact_phone=None),
    dict(commune_code="tua_chua", name="Trường THPT Tủa Chùa",
         address="TT Tủa Chùa, huyện Tủa Chùa", lat=21.9915, lon=103.3585,
         capacity=400, kind=ShelterKind.school, contact_phone=None),
    dict(commune_code="tua_chua", name="Nhà văn hoá huyện Tủa Chùa",
         address="TT Tủa Chùa", lat=21.9885, lon=103.3620,
         capacity=250, kind=ShelterKind.community_hall, contact_phone=None),
    dict(commune_code="nam_po", name="Trạm y tế xã Nậm Pồ",
         address="Trung tâm xã Nậm Pồ", lat=21.9905, lon=102.7215,
         capacity=80, kind=ShelterKind.health_station, contact_phone=None),
    dict(commune_code="tuan_giao", name="UBND thị trấn Tuần Giáo",
         address="TT Tuần Giáo", lat=21.5815, lon=103.4185,
         capacity=180, kind=ShelterKind.commune_office, contact_phone=None),
]


class ShelterStore:
    def __init__(self) -> None:
        self._by_id: dict[str, Shelter] = {}
        for s in _SEED:
            self._add(ShelterCreate(**s))  # seed KHÔNG mirror (tránh gọi mạng lúc import)

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
