"""Tool tra cứu / recommend hành động — KB theo (hazard, cấp) + đặc thù xã.

Seed base action từ risk_engine._ACTIONS, bổ sung hành động leo thang theo cấp và
theo địa hình (độ nhạy cảm sạt lở). Chỗ để cắm vector-search RAG lịch sử thiên tai sau.
"""

from __future__ import annotations

from agent_worker.shared.common import Hazard, risk_meta

from agent_worker.ai.risk_engine import _ACTIONS as _BASE_ACTIONS

# Hành động thêm khi cấp cao (>=3: cam trở lên) — mọi loại hình.
_ESCALATION_HIGH = [
    "Sẵn sàng SƠ TÁN theo hiệu lệnh của trưởng bản/cán bộ xã",
    "Mang theo giấy tờ, thuốc men, nước uống khi di chuyển",
]
# Hành động thêm cho xã nhạy cảm sạt lở cao.
_HIGH_SUSC = ["Không ở lại nhà chân đồi/ta-luy dốc khi trời còn mưa"]


def _base(hazard: str) -> list[str]:
    for hz, actions in _BASE_ACTIONS.items():
        if hz.value == hazard:
            return list(actions)
    return []


def lookup(hazard: str, level: int, commune: dict) -> list[str]:
    """Danh sách hành động khuyến nghị cho 1 (hazard, cấp) tại 1 xã."""
    actions = _base(hazard)
    if level >= 3:
        actions += _ESCALATION_HIGH
    if (commune or {}).get("landslide_susceptibility") == "high" and hazard in (
        Hazard.flash_flood.value, Hazard.landslide.value, Hazard.heavy_rain.value,
    ):
        actions += _HIGH_SUSC
    # loại trùng, giữ thứ tự
    seen: set[str] = set()
    return [a for a in actions if not (a in seen or seen.add(a))]


def to_scale(level: int) -> dict:
    """Thang QĐ18 cho UI trực quan: màu + emoji + nhãn (icon thay chữ kỹ thuật)."""
    meta = risk_meta(level)
    return {"level": int(level), "color": meta["color"],
            "emoji": meta["emoji"], "label": meta["label_vi"]}
