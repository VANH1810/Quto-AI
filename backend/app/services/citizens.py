"""DB1 — Kho công dân (in-memory). Khoá = CCCD.

Interface tách riêng để sau thay bằng nguồn dữ liệu dân cư quốc gia / Postgres mà
không đụng route. `fetch_from_state()` mô phỏng việc đồng bộ từ CSDL nhà nước.
"""

from __future__ import annotations

from app.schemas.citizen import Citizen, CitizenCreate, lang_from_ethnicity
from app.services import supabase_repo


class CitizenStore:
    def __init__(self) -> None:
        self._by_cccd: dict[str, Citizen] = {}

    def upsert(self, data: CitizenCreate, mirror: bool = True) -> Citizen:
        citizen = Citizen(
            id=data.cccd,
            preferred_lang=lang_from_ethnicity(data.ethnicity),
            **data.model_dump(),
        )
        self._by_cccd[data.cccd] = citizen
        if mirror:  # seed hàng loạt truyền mirror=False rồi đẩy 1 lần cho nhanh
            supabase_repo.mirror(supabase_repo.push_citizens, [citizen])
        return citizen

    def get(self, cccd: str) -> Citizen | None:
        return self._by_cccd.get(cccd)

    def all(self) -> list[Citizen]:
        return list(self._by_cccd.values())

    def by_commune(self, commune_code: str) -> list[Citizen]:
        return [c for c in self._by_cccd.values() if c.commune_code == commune_code]

    def contactable(self, commune_code: str, channel: str) -> list[Citizen]:
        """Người nhận hợp lệ cho 1 kênh ở 1 xã (tôn trọng consent NĐ13/2023).

        Loa phát thanh phát ra không gian công cộng → không cần consent cá nhân.
        """
        people = self.by_commune(commune_code)
        if channel in ("zalo_zns", "sms"):
            return [c for c in people if c.consent_zalo_sms and c.phone]
        return people


citizens = CitizenStore()
