"""Kiểu chung: cấp độ rủi ro (thang màu QĐ18/2021), loại hình thiên tai, kênh, ngôn ngữ.

Vendor từ backend/app/schemas/common.py — giữ đồng bộ khi backend đổi.
"""

from __future__ import annotations

from enum import IntEnum, Enum


class RiskLevel(IntEnum):
    """Cấp độ rủi ro thiên tai theo QĐ18/2021/QĐ-TTg (thang 5 màu)."""

    NONE = 0
    LOW = 1
    MEDIUM = 2
    LARGE = 3
    VERY_LARGE = 4
    CATASTROPHE = 5


RISK_META: dict[int, dict[str, str]] = {
    0: {"color": "#16a34a", "label_vi": "Bình thường", "emoji": "🟢"},
    1: {"color": "#38bdf8", "label_vi": "Cấp 1 · Nhỏ", "emoji": "🔵"},
    2: {"color": "#eab308", "label_vi": "Cấp 2 · Trung bình", "emoji": "🟡"},
    3: {"color": "#f97316", "label_vi": "Cấp 3 · Lớn", "emoji": "🟠"},
    4: {"color": "#dc2626", "label_vi": "Cấp 4 · Rất lớn", "emoji": "🔴"},
    5: {"color": "#7c3aed", "label_vi": "Cấp 5 · Thảm họa", "emoji": "🟣"},
}


class Hazard(str, Enum):
    flash_flood = "flash_flood"
    landslide = "landslide"
    heavy_rain = "heavy_rain"
    frost = "frost"
    fog = "fog"


HAZARD_META: dict[str, dict[str, str]] = {
    "flash_flood": {"label_vi": "Lũ quét", "emoji": "🌊"},
    "landslide": {"label_vi": "Sạt lở đất", "emoji": "⛰️"},
    "heavy_rain": {"label_vi": "Mưa lớn", "emoji": "🌧️"},
    "frost": {"label_vi": "Rét hại / Sương muối", "emoji": "❄️"},
    "fog": {"label_vi": "Sương mù", "emoji": "🌫️"},
}


class Channel(str, Enum):
    zalo_zns = "zalo_zns"
    sms = "sms"
    loudspeaker = "loudspeaker"


class Lang(str, Enum):
    vi = "vi"
    tai = "tai"
    hmn = "hmn"


def risk_meta(level: int) -> dict[str, str]:
    return RISK_META.get(int(level), RISK_META[0])
