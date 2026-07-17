"""Sinh dữ liệu mẫu TẤT ĐỊNH: nhiều công dân theo từng xã + 1 admin cho MỖI xã.

Không dùng random (tái lập được). Tên/dân tộc phân bố theo vùng: vùng cao thiên về
Mông, thung lũng/phường thiên về Thái–Kinh, Sín Thầu có Hà Nhì.
"""

from __future__ import annotations

from app.schemas.admin import AdminCreate, AdminRole
from app.schemas.citizen import CitizenCreate
from app.services.geo_data import all_communes

_THAI_HO = ["Lò", "Lường", "Quàng", "Cà", "Tòng", "Lù", "Điêu", "Vì"]
_THAI_M = ["Văn Panh", "Văn Inh", "Văn Pâng", "Văn Hặc", "Văn Muôn", "Văn Sơn", "Văn Thoong", "Văn Đại"]
_THAI_F = ["Thị Ánh", "Thị Muôn", "Thị Ơn", "Thị Hặc", "Thị Inh", "Thị Panh", "Thị Nọi", "Thị Loan"]
_MONG_HO = ["Vàng", "Giàng", "Sùng", "Thào", "Lý", "Hạng", "Mùa", "Cứ", "Sính"]
_MONG_M = ["A Sùng", "A Chá", "A Dơ", "A Lử", "A Vàng", "A Dua", "A Tráng", "A Chống"]
_MONG_F = ["Thị Mai", "Thị Dua", "Thị Chù", "Thị Xúa", "Thị Dở", "Thị Máy", "Thị Say", "Thị Chá"]
_KINH_HO = ["Nguyễn", "Trần", "Lê", "Phạm", "Hoàng", "Vũ", "Đặng", "Bùi"]
_KINH_M = ["Văn Bình", "Văn Nam", "Văn Hùng", "Văn Dũng", "Văn Thành", "Văn Long", "Văn Tú", "Văn Quang"]
_KINH_F = ["Thị Hoa", "Thị Lan", "Thị Thu", "Thị Hương", "Thị Nga", "Thị Yến", "Thị Vân", "Thị Hằng"]
_HANHI_HO = ["Pờ", "Sùng", "Lỳ", "Chang", "Gò"]
_HANHI_M = ["Á Tư", "Xè Lù", "Gạ Mờ", "Chừ Cà"]
_HANHI_F = ["Xì Mế", "Nhù Cà", "Á Mý", "Cà Nhè"]

_POOLS = {
    "Thái": (_THAI_HO, _THAI_M, _THAI_F),
    "Mông": (_MONG_HO, _MONG_M, _MONG_F),
    "Kinh": (_KINH_HO, _KINH_M, _KINH_F),
    "Hà Nhì": (_HANHI_HO, _HANHI_M, _HANHI_F),
}

_BANS = ["Nà Pen", "Huổi Lóng", "Pá Khoang", "Co Mỵ", "Xôm", "Loọng", "Huổi Chan",
         "Nậm Pố", "Phiêng Ban", "Tà Lèng", "Hô Nậm Cản", "Kê Nênh"]


def _full_name(ethnicity: str, k: int) -> str:
    ho, male, female = _POOLS.get(ethnicity, _POOLS["Kinh"])
    given = male if k % 2 == 0 else female
    return f"{ho[k % len(ho)]} {given[(k // 2) % len(given)]}"


def _ethnic_pool(commune) -> list[str]:
    """Danh sách 10 dân tộc để xoay vòng theo tỉ lệ vùng."""
    code = commune.code
    if code in ("dien_bien_phu", "muong_thanh", "muong_lay"):
        return ["Kinh"] * 5 + ["Thái"] * 4 + ["Mông"] * 1
    if code == "sin_thau":
        return ["Hà Nhì"] * 7 + ["Mông"] * 2 + ["Kinh"] * 1
    if commune.elevation_m >= 900:
        return ["Mông"] * 6 + ["Thái"] * 3 + ["Kinh"] * 1
    return ["Thái"] * 6 + ["Kinh"] * 2 + ["Mông"] * 2


def generate_citizens(per_commune: int = 10) -> list[CitizenCreate]:
    out: list[CitizenCreate] = []
    for ci, commune in enumerate(all_communes()):
        pool = _ethnic_pool(commune)
        for i in range(per_commune):
            eth = pool[i % 10]
            out.append(CitizenCreate(
                cccd=f"011{ci:02d}{i:07d}",
                full_name=_full_name(eth, ci * 7 + i),
                age=18 + ((ci * 13 + i * 7) % 55),
                address=f"Bản {_BANS[(ci + i) % len(_BANS)]}, {commune.name}",
                phone="09" + f"{(ci * 10000 + i * 137) % 100000000:08d}",
                ethnicity=eth, religion=None, commune_code=commune.code,
                lat=round(commune.lat + ((i % 5) - 2) * 0.004, 6),
                lon=round(commune.lon + (((i // 5) % 5) - 2) * 0.004, 6),
                consent_zalo_sms=((ci + i) % 7 != 0),  # ~1/7 chưa đồng ý → chỉ nhận qua loa
            ))
    return out


def generate_admins() -> list[AdminCreate]:
    """1 cán bộ cho MỖI xã (role=commune, phụ trách đúng xã đó). Mật khẩu demo: 123456."""
    out: list[AdminCreate] = []
    for ci, commune in enumerate(all_communes()):
        eth = "Thái" if commune.elevation_m < 900 else "Mông"
        out.append(AdminCreate(
            email=f"canbo.{commune.code}@dienbien.gov.vn", password="123456",
            full_name=_full_name(eth, ci * 3), age=30 + (ci % 25),
            phone="0961" + f"{ci:06d}", ethnicity=eth,
            role=AdminRole.commune, communes=[commune.code],
        ))
    return out
