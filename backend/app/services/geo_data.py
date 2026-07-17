"""Danh mục xã Điện Biên + toạ độ cho bản đồ (seed cứng cho demo).

Toạ độ/độ cao là xấp xỉ phục vụ trình diễn; sản phẩm thật nạp từ ranh giới
hành chính chính thức (PostGIS) + DEM Copernicus GLO-90.

Mức nhạy cảm lũ quét/sạt lở (landslide_susceptibility) theo tinh thần QĐ18/2021:
Điện Biên thuộc Khu vực 1 (nhạy cảm cao nhất).
"""

from __future__ import annotations

import math

from app.schemas.geo import Commune


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Khoảng cách đường chim bay (km) giữa 2 toạ độ — dùng tìm nơi trú ẩn gần nhất."""
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlmb = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlmb / 2) ** 2
    return round(2 * r * math.asin(math.sqrt(a)), 2)

# code, name, district, lat, lon, elevation_m, susceptibility, population
_COMMUNES: list[Commune] = [
    Commune(code="muong_pon", name="Xã Mường Pồn", district="Điện Biên",
            lat=21.5300, lon=103.0800, elevation_m=720, landslide_susceptibility="high", population=3200),
    Commune(code="tua_chua", name="Thị trấn Tủa Chùa", district="Tủa Chùa",
            lat=21.9900, lon=103.3600, elevation_m=1420, landslide_susceptibility="high", population=6100),
    Commune(code="muong_nhe", name="Xã Mường Nhé", district="Mường Nhé",
            lat=22.1800, lon=102.4700, elevation_m=900, landslide_susceptibility="medium", population=5400),
    Commune(code="nam_po", name="Xã Nậm Pồ", district="Nậm Pồ",
            lat=21.9900, lon=102.7200, elevation_m=820, landslide_susceptibility="high", population=4300),
    Commune(code="tuan_giao", name="Thị trấn Tuần Giáo", district="Tuần Giáo",
            lat=21.5800, lon=103.4200, elevation_m=600, landslide_susceptibility="medium", population=8700),
    Commune(code="dbp", name="TP Điện Biên Phủ", district="Điện Biên Phủ",
            lat=21.3860, lon=103.0170, elevation_m=480, landslide_susceptibility="low", population=80000),
    Commune(code="muong_cha", name="Thị trấn Mường Chà", district="Mường Chà",
            lat=21.8500, lon=103.1000, elevation_m=650, landslide_susceptibility="medium", population=4100),
    Commune(code="dien_bien_dong", name="Thị trấn Điện Biên Đông", district="Điện Biên Đông",
            lat=21.2800, lon=103.2000, elevation_m=900, landslide_susceptibility="high", population=3800),
]

_BY_CODE: dict[str, Commune] = {c.code: c for c in _COMMUNES}


def all_communes() -> list[Commune]:
    return list(_COMMUNES)


def get_commune(code: str) -> Commune | None:
    return _BY_CODE.get(code)
