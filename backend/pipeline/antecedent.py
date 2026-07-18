"""Antecedent precipitation bookkeeping (D2/D3 of the spec, adapter side).

State is one JSON file per commune under state/antecedent/ holding daily rain
totals keyed by LOCAL (Asia/Ho_Chi_Minh) date. Everything the engine reads
(rain_days_prior, api_mm, days_since_data_gap) is recomputed deterministically
from that history each tick — never fabricated when history is short.
"""

from __future__ import annotations

import json
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Mapping
from zoneinfo import ZoneInfo

API_DECAY_K = 0.85
HISTORY_KEEP_DAYS = 30
GAP_CAP_DAYS = 14


def daily_totals_from_hourly(
    times: list[str], precip: list[float | None], zone_name: str
) -> dict[str, float]:
    """Complete local days only; a day with missing hours is a gap, not a zero."""
    zone = ZoneInfo(zone_name)
    by_day: dict[str, list[float | None]] = {}
    for stamp, value in zip(times, precip):
        parsed = datetime.fromisoformat(stamp.replace("Z", "+00:00"))
        local_day = parsed.astimezone(zone).date().isoformat()
        by_day.setdefault(local_day, []).append(value)
    return {
        day: round(sum(float(v) for v in values), 2)
        for day, values in by_day.items()
        if len(values) == 24 and all(v is not None for v in values)
    }


def compute_block(
    daily_mm: Mapping[str, float],
    today_local: date,
    rain_day_threshold_mm: float,
) -> dict[str, Any]:
    """The exact RiskEngineInput.antecedent fields from stored daily history."""
    api = 0.0
    for day in sorted(daily_mm):
        if date.fromisoformat(day) < today_local:
            api = API_DECAY_K * api + daily_mm[day]

    rain_days = 0
    cursor = today_local - timedelta(days=1)
    while daily_mm.get(cursor.isoformat(), -1.0) >= rain_day_threshold_mm:
        rain_days += 1
        cursor -= timedelta(days=1)

    complete_days = 0
    cursor = today_local - timedelta(days=1)
    while cursor.isoformat() in daily_mm and complete_days < GAP_CAP_DAYS:
        complete_days += 1
        cursor -= timedelta(days=1)

    return {
        "rain_days_prior": rain_days,
        "rain_day_threshold_mm": rain_day_threshold_mm,
        "api_mm": round(api, 2),
        "days_since_data_gap": complete_days,
    }


def load_history(state_dir: Path, commune_code: str) -> dict[str, float]:
    path = state_dir / "antecedent" / f"{commune_code}.json"
    if not path.is_file():
        return {}
    return dict(json.loads(path.read_text(encoding="utf-8"))["daily_mm"])


def merge_history(
    history: Mapping[str, float], new_daily: Mapping[str, float]
) -> dict[str, float]:
    merged = {**history, **new_daily}
    keep = sorted(merged)[-HISTORY_KEEP_DAYS:]
    return {day: merged[day] for day in keep}


def save_history(
    state_dir: Path, commune_code: str, daily_mm: Mapping[str, float], updated_at: str
) -> None:
    directory = state_dir / "antecedent"
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"{commune_code}.json"
    payload = {
        "commune_code": commune_code,
        "daily_mm": dict(sorted(daily_mm.items())),
        "updated_at": updated_at,
    }
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    tmp.replace(path)
