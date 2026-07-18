"""Danh mục 45 xã/phường Điện Biên (sau sắp xếp ĐVHC 2025) + toạ độ + haversine.

Vendor từ backend/app/services/geo_data.py. Toạ độ/độ cao XẤP XỈ theo khu vực (former
district) để trình diễn + hiệu chỉnh rét hại theo độ cao; sản phẩm thật nạp ranh giới
chính thức (PostGIS) + DEM Copernicus GLO-90. Mức nhạy cảm lũ quét/sạt lở theo tinh
thần QĐ18/2021 (Điện Biên thuộc Khu vực 1 — nhạy cảm cao).
"""

from __future__ import annotations

import math

from agent_worker.shared.geo import Commune


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlmb = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlmb / 2) ** 2
    return round(2 * r * math.asin(math.sqrt(a)), 2)


# (code, name, khu vực, lat, lon, elevation_m, susceptibility, population)
_RAW: list[tuple] = [
    ("muong_nhe", "Xã Mường Nhé", "Mường Nhé", 22.180, 102.470, 900, "high", 5400),
    ("sin_thau", "Xã Sín Thầu", "Mường Nhé", 22.370, 102.180, 1200, "high", 2100),
    ("muong_toong", "Xã Mường Toong", "Mường Nhé", 22.200, 102.550, 950, "high", 4200),
    ("nam_ke", "Xã Nậm Kè", "Mường Nhé", 22.050, 102.600, 850, "high", 3600),
    ("quang_lam", "Xã Quảng Lâm", "Mường Nhé", 22.000, 102.550, 900, "high", 3300),
    ("na_hy", "Xã Nà Hỳ", "Nậm Pồ", 21.950, 102.720, 800, "high", 4300),
    ("na_bung", "Xã Nà Bủng", "Nậm Pồ", 21.800, 102.650, 850, "high", 3900),
    ("cha_to", "Xã Chà Tở", "Nậm Pồ", 21.880, 102.850, 780, "high", 3100),
    ("si_pa_phin", "Xã Si Pa Phìn", "Nậm Pồ", 21.830, 102.900, 900, "high", 5200),
    ("muong_cha", "Xã Mường Chà", "Mường Chà", 21.850, 103.100, 650, "medium", 6100),
    ("na_sang", "Xã Na Sang", "Mường Chà", 21.780, 103.050, 600, "medium", 4000),
    ("muong_tung", "Xã Mường Tùng", "Mường Chà", 21.900, 103.150, 700, "medium", 3400),
    ("pa_ham", "Xã Pa Ham", "Mường Chà", 21.950, 103.250, 750, "medium", 3200),
    ("nam_nen", "Xã Nậm Nèn", "Mường Chà", 21.720, 103.020, 700, "medium", 2800),
    ("muong_pon", "Xã Mường Pồn", "Điện Biên", 21.530, 103.080, 720, "high", 3200),
    ("tua_chua", "Xã Tủa Chùa", "Tủa Chùa", 21.990, 103.360, 1420, "high", 6100),
    ("sin_chai", "Xã Sín Chải", "Tủa Chùa", 22.080, 103.330, 1500, "high", 3800),
    ("sinh_phinh", "Xã Sính Phình", "Tủa Chùa", 22.020, 103.400, 1450, "high", 4100),
    ("tua_thang", "Xã Tủa Thàng", "Tủa Chùa", 21.920, 103.450, 1100, "high", 4600),
    ("sang_nhe", "Xã Sáng Nhè", "Tủa Chùa", 21.880, 103.380, 1000, "high", 3500),
    ("tuan_giao", "Xã Tuần Giáo", "Tuần Giáo", 21.580, 103.420, 600, "medium", 8700),
    ("quai_to", "Xã Quài Tở", "Tuần Giáo", 21.620, 103.500, 700, "medium", 4200),
    ("muong_mun", "Xã Mường Mùn", "Tuần Giáo", 21.650, 103.350, 650, "medium", 4900),
    ("pu_nhung", "Xã Pú Nhung", "Tuần Giáo", 21.720, 103.420, 900, "high", 3600),
    ("chieng_sinh", "Xã Chiềng Sinh", "Tuần Giáo", 21.550, 103.480, 650, "medium", 5100),
    ("muong_ang", "Xã Mường Ảng", "Mường Ảng", 21.500, 103.320, 550, "low", 7200),
    ("na_tau", "Xã Nà Tấu", "Điện Biên", 21.480, 103.180, 700, "medium", 4300),
    ("bung_lao", "Xã Búng Lao", "Mường Ảng", 21.550, 103.250, 600, "medium", 4100),
    ("muong_lan", "Xã Mường Lạn", "Mường Ảng", 21.450, 103.200, 650, "medium", 3800),
    ("muong_phang", "Xã Mường Phăng", "Điện Biên", 21.420, 103.150, 950, "medium", 4400),
    ("thanh_nua", "Xã Thanh Nưa", "Điện Biên", 21.450, 103.000, 500, "low", 5200),
    ("thanh_an", "Xã Thanh An", "Điện Biên", 21.330, 103.020, 480, "low", 6300),
    ("thanh_yen", "Xã Thanh Yên", "Điện Biên", 21.350, 103.050, 480, "low", 6000),
    ("sam_mun", "Xã Sam Mứn", "Điện Biên", 21.300, 103.000, 480, "low", 5500),
    ("nua_ngam", "Xã Núa Ngam", "Điện Biên", 21.250, 102.950, 550, "medium", 4200),
    ("muong_nha", "Xã Mường Nhà", "Điện Biên", 21.150, 103.050, 600, "medium", 3900),
    ("na_son", "Xã Na Son", "Điện Biên Đông", 21.280, 103.220, 900, "high", 4600),
    ("xa_dung", "Xã Xa Dung", "Điện Biên Đông", 21.200, 103.300, 1100, "high", 3300),
    ("pu_nhi", "Xã Pu Nhi", "Điện Biên Đông", 21.220, 103.250, 1000, "high", 3700),
    ("muong_luan", "Xã Mường Luân", "Điện Biên Đông", 21.100, 103.400, 700, "medium", 4000),
    ("tia_dinh", "Xã Tia Dình", "Điện Biên Đông", 21.150, 103.450, 800, "high", 3100),
    ("phinh_giang", "Xã Phình Giàng", "Điện Biên Đông", 21.180, 103.350, 950, "high", 3400),
    ("muong_lay", "Phường Mường Lay", "Mường Lay", 22.030, 103.150, 200, "medium", 12000),
    ("dien_bien_phu", "Phường Điện Biên Phủ", "Điện Biên Phủ", 21.386, 103.017, 480, "low", 55000),
    ("muong_thanh", "Phường Mường Thanh", "Điện Biên Phủ", 21.380, 103.020, 480, "low", 42000),
]

_COMMUNES: list[Commune] = [
    Commune(code=c, name=n, district=d, lat=lat, lon=lon,
            elevation_m=elev, landslide_susceptibility=sus, population=pop)
    for (c, n, d, lat, lon, elev, sus, pop) in _RAW
]

_BY_CODE: dict[str, Commune] = {c.code: c for c in _COMMUNES}


def all_communes() -> list[Commune]:
    return list(_COMMUNES)


def get_commune(code: str) -> Commune | None:
    return _BY_CODE.get(code)


def nearest_commune(lat: float, lon: float) -> Commune:
    """Xã gần toạ độ nhất — suy xã cho tin SOS khi người gặp nạn không biết mã xã."""
    return min(_COMMUNES, key=lambda c: haversine_km(lat, lon, c.lat, c.lon))
