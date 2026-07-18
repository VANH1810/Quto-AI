from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

TIMEZONE = "Asia/Ho_Chi_Minh"


def apply_qm(
    commune_code: str,
    times: list[str],
    hourly_precip: list[float | None],
    qm_dir: Path,
) -> tuple[list[float | None], str]:
    """Corrected hourly precip + mode ("identity" or "qm_v1")."""
    artifact = qm_dir / f"qm_{commune_code}.json"
    if not artifact.is_file():
        return list(hourly_precip), "identity"
    pairs = json.loads(artifact.read_text(encoding="utf-8"))
    forecast_q = pairs["quantiles_forecast"]
    truth_q = pairs["quantiles_truth"]

    zone = ZoneInfo(TIMEZONE)
    day_keys = [
        datetime.fromisoformat(t.replace("Z", "+00:00")).astimezone(zone).date()
        for t in times
    ]
    factors = {
        day: _daily_factor(
            sum(float(v or 0.0) for v, d in zip(hourly_precip, day_keys) if d == day),
            forecast_q,
            truth_q,
        )
        for day in set(day_keys)
    }
    corrected = [
        None if value is None else round(float(value) * factors[day], 4)
        for value, day in zip(hourly_precip, day_keys)
    ]
    return corrected, "qm_v1"


def _daily_factor(total: float, forecast_q: list[float], truth_q: list[float]) -> float:
    if total <= 0.0:
        return 1.0
    return _interp(total, forecast_q, truth_q) / total


def _interp(value: float, xs: list[float], ys: list[float]) -> float:
    if value <= xs[0]:
        return ys[0] if xs[0] <= 0 else value * (ys[0] / xs[0] if xs[0] else 1.0)
    if value >= xs[-1]:
        # extrapolate with the last segment's ratio, never a flat cap
        return value * (ys[-1] / xs[-1] if xs[-1] else 1.0)
    for left in range(len(xs) - 1):
        if xs[left] <= value <= xs[left + 1]:
            span = xs[left + 1] - xs[left]
            weight = 0.0 if span == 0 else (value - xs[left]) / span
            return ys[left] + weight * (ys[left + 1] - ys[left])
    return value
