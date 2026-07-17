"""Risk engine TẤT ĐỊNH theo QĐ18/2021/QĐ-TTg — KHÔNG dùng LLM.

Vào: ForecastResponse (đã hạ quy mô về xã) + đặc trưng địa hình (độ cao, độ nhạy
cảm sạt lở). Ra: danh sách HazardEvent với cấp độ 1..5, dòng provenance (số liệu
cụ thể đã vượt ngưỡng) + hành động khuyến nghị.

Ngưỡng để ở RULES (chỉnh được, có thể đưa ra .env/DB) → minh bạch, kiểm toán được.
"""

from __future__ import annotations

from dataclasses import dataclass

from agent_worker.shared.alert import HazardEvent, Provenance
from agent_worker.shared.common import Hazard, risk_meta
from agent_worker.shared.forecast import DailyForecast, ForecastResponse
from agent_worker.shared.geo import Commune


@dataclass(frozen=True)
class Rules:
    # Mưa lớn (mm/24h): QĐ18 — >50 mưa to; >100 mưa rất to.
    heavy_rain_to: float = 50
    heavy_rain_rat_to: float = 100
    # Lũ quét/sạt lở Khu vực 1 (mm/24h) — kết hợp mưa dồn + nhạy cảm địa hình.
    ff_l1: float = 100
    ff_l2: float = 200
    ff_l3: float = 400
    antecedent_days: int = 2       # số ngày mưa liền trước tính 'đất bão hoà'
    antecedent_rain_mm: float = 20  # ngưỡng coi 1 ngày là 'có mưa đáng kể'
    # Rét hại / sương muối: QĐ18 — nhiệt TB ngày <13°C = rét hại.
    ret_hai_mean: float = 13
    ret_dam_mean: float = 8
    frost_min_c: float = 2         # sương muối khi nhiệt tối thấp <=2°C, trời quang
    # Sương mù ảnh hưởng giao thông (tầm nhìn m).
    fog_vis_m: float = 500


RULES = Rules()

# Hệ số cộng cấp theo độ nhạy cảm sạt lở của xã.
_SUSC_BUMP = {"low": 0, "medium": 0, "high": 1}

_ACTIONS = {
    Hazard.flash_flood: ["Rời ngay khỏi bờ suối, khe cạn", "Di chuyển lên chỗ cao",
                         "Không qua ngầm tràn khi nước dâng", "Trưởng bản kiểm tra hộ ven suối"],
    Hazard.landslide: ["Tránh xa mái dốc, ta-luy", "Quan sát vết nứt trên đồi",
                       "Sẵn sàng sơ tán khi có tiếng động lạ"],
    Hazard.heavy_rain: ["Che chắn nhà cửa, khơi thông cống rãnh", "Hạn chế ra đường",
                        "Bảo vệ mạ, hoa màu"],
    Hazard.frost: ["Giữ ấm người già, trẻ nhỏ", "Che chắn, đốt sưởi cho gia súc",
                   "Phủ ấm mạ non, không chăn thả sáng sớm"],
    Hazard.fog: ["Bật đèn, đi chậm, giữ khoảng cách", "Hạn chế xe máy đường đèo lúc sáng sớm"],
}


def _antecedent_wet_days(days: list[DailyForecast], upto: int) -> int:
    lo = max(0, upto - RULES.antecedent_days)
    return sum(1 for d in days[lo:upto] if d.precip_mm >= RULES.antecedent_rain_mm)


def _mk_event(hazard: Hazard, commune: Commune, level: int, day: DailyForecast,
              source: str, rule: str, triggered: dict) -> HazardEvent:
    rm = risk_meta(level)
    return HazardEvent(
        hazard=hazard.value, commune_code=commune.code, commune_name=commune.name,
        risk_level=level, risk_color=rm["color"], risk_label=rm["label_vi"],
        provenance=Provenance(source=source, rule=rule, triggered_by=triggered,
                              observed_at=day.date),
        recommended_actions=_ACTIONS[hazard],
    )


def evaluate(forecast: ForecastResponse, commune: Commune) -> list[HazardEvent]:
    """Chấm toàn bộ chuỗi ngày → trả các HazardEvent (đã gộp lấy cấp cao nhất/loại)."""
    best: dict[str, HazardEvent] = {}

    def consider(ev: HazardEvent) -> None:
        cur = best.get(ev.hazard)
        if cur is None or ev.risk_level > cur.risk_level:
            best[ev.hazard] = ev

    bump = _SUSC_BUMP.get(commune.landslide_susceptibility, 0)

    for i, day in enumerate(forecast.days):
        p = day.precip_mm
        wet = _antecedent_wet_days(forecast.days, i)
        saturated = wet >= RULES.antecedent_days

        # --- Lũ quét / sạt lở (Khu vực 1) ---
        # QĐ18: 100–200mm→cơ sở cấp 1, 200–400→cấp 2, >400→cấp 3; cộng cấp khi
        # đất đã bão hoà (mưa dồn nhiều ngày) + xã nhạy cảm sạt lở cao.
        base = 3 if p >= RULES.ff_l3 else 2 if p >= RULES.ff_l2 else 1 if p >= RULES.ff_l1 else 0
        if base:
            ff_level = min(4, base + (1 if saturated else 0) + bump)
            trig = {"precip_24h_mm": p, "antecedent_wet_days": wet,
                    "soil": "bão hoà" if saturated else "chưa bão hoà",
                    "susceptibility": commune.landslide_susceptibility}
            consider(_mk_event(Hazard.flash_flood, commune, ff_level, day,
                               forecast.source, f"QĐ18 lũ quét/sạt lở KV1 · mức {ff_level}", trig))

        # --- Mưa lớn ---
        if p >= RULES.heavy_rain_rat_to:
            consider(_mk_event(Hazard.heavy_rain, commune, 2, day, forecast.source,
                               "QĐ18 mưa rất to (>100mm/24h)", {"precip_24h_mm": p}))
        elif p >= RULES.heavy_rain_to:
            consider(_mk_event(Hazard.heavy_rain, commune, 1, day, forecast.source,
                               "QĐ18 mưa to (>50mm/24h)", {"precip_24h_mm": p}))

        # --- Rét hại / sương muối ---
        if day.temp_mean_c < RULES.ret_dam_mean:
            consider(_mk_event(Hazard.frost, commune, 2, day, forecast.source,
                               "QĐ18 rét đậm/hại (TB<8°C)",
                               {"temp_mean_c": day.temp_mean_c, "temp_min_c": day.temp_min_c}))
        elif day.temp_mean_c < RULES.ret_hai_mean:
            lvl = 2 if day.temp_min_c <= RULES.frost_min_c else 1
            consider(_mk_event(Hazard.frost, commune, lvl, day, forecast.source,
                               "QĐ18 rét hại (TB<13°C)" + (" + nguy cơ sương muối" if lvl == 2 else ""),
                               {"temp_mean_c": day.temp_mean_c, "temp_min_c": day.temp_min_c}))

        # --- Sương mù (giao thông) ---
        if day.visibility_min_m is not None and day.visibility_min_m < RULES.fog_vis_m:
            consider(_mk_event(Hazard.fog, commune, 1, day, forecast.source,
                               "Tầm nhìn < 500m", {"visibility_min_m": day.visibility_min_m}))

    return list(best.values())


def top_event(events: list[HazardEvent]) -> HazardEvent | None:
    return max(events, key=lambda e: e.risk_level) if events else None
