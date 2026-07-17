"""Kiểu chung: cấp độ rủi ro (thang màu QĐ18/2021), loại hình thiên tai, kênh, ngôn ngữ."""

from __future__ import annotations

from enum import IntEnum, Enum


class RiskLevel(IntEnum):
    """Cấp độ rủi ro thiên tai theo QĐ18/2021/QĐ-TTg (thang 5 màu)."""

    NONE = 0        # bình thường
    LOW = 1         # xanh nhạt — nhỏ
    MEDIUM = 2      # vàng — trung bình
    LARGE = 3       # cam — lớn
    VERY_LARGE = 4  # đỏ — rất lớn
    CATASTROPHE = 5 # tím — thảm họa


# Thang màu + nhãn chính thức, dùng chung cho UI/bản tin.
RISK_META: dict[int, dict[str, str]] = {
    0: {"color": "#16a34a", "label_vi": "Bình thường", "emoji": "🟢"},
    1: {"color": "#38bdf8", "label_vi": "Cấp 1 · Nhỏ", "emoji": "🔵"},
    2: {"color": "#eab308", "label_vi": "Cấp 2 · Trung bình", "emoji": "🟡"},
    3: {"color": "#f97316", "label_vi": "Cấp 3 · Lớn", "emoji": "🟠"},
    4: {"color": "#dc2626", "label_vi": "Cấp 4 · Rất lớn", "emoji": "🔴"},
    5: {"color": "#7c3aed", "label_vi": "Cấp 5 · Thảm họa", "emoji": "🟣"},
}


class Hazard(str, Enum):
    """Loại hình thiên tai xử lý trong hệ."""

    flash_flood = "flash_flood"    # lũ quét
    landslide = "landslide"        # sạt lở đất
    heavy_rain = "heavy_rain"      # mưa lớn
    frost = "frost"                # rét hại / sương muối
    fog = "fog"                    # sương mù (giao thông)


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
    """Ngôn ngữ bản tin. Mã TTS Meta MMS đi kèm ở providers/tts.py."""

    vi = "vi"     # Tiếng Việt
    tai = "tai"   # Thái (Tai Dam) — MMS 'blt'
    hmn = "hmn"   # Mông/Hmong (Hmong Daw) — MMS 'mww'


def risk_meta(level: int) -> dict[str, str]:
    return RISK_META.get(int(level), RISK_META[0])
