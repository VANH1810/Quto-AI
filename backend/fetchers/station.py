"""Station observation seam.

Mode "csv" reads `timestamp,commune_code,rain_1h,temp,rh,wind` rows.
Mode "none" (default) returns None per commune: the engine's own degraded-data
guardrails then apply. We deliberately do NOT emit a block with
quality="missing" — the engine recomputes quality from observed_at age and a
recent timestamp would surface as data_quality.observations="fresh", which
would misreport a station we do not have (see REPORT.md contract questions).
"""

from __future__ import annotations

import csv
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterable

# csv format: timestamp,commune_code,rain_1h,temp,rh,wind
CSV_FIELDS = ("timestamp", "commune_code", "rain_1h", "temp", "rh", "wind")


def load_observations(
    mode: str,
    csv_path: Path | None,
    commune_codes: Iterable[str],
    tick_time: datetime,
) -> dict[str, dict[str, Any] | None]:
    if mode == "none":
        return {code: None for code in commune_codes}
    if mode != "csv" or csv_path is None:
        raise ValueError(f"unknown station mode {mode!r} (use 'none' or 'csv')")
    rows = _read_rows(csv_path)
    return {
        code: _observation_block(rows.get(code, []), tick_time)
        for code in commune_codes
    }


def _read_rows(csv_path: Path) -> dict[str, list[dict[str, Any]]]:
    by_commune: dict[str, list[dict[str, Any]]] = {}
    with csv_path.open(encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            parsed = dict(row)
            parsed["timestamp"] = datetime.fromisoformat(
                row["timestamp"].replace("Z", "+00:00")
            ).astimezone(timezone.utc)
            by_commune.setdefault(row["commune_code"], []).append(parsed)
    for rows in by_commune.values():
        rows.sort(key=lambda item: item["timestamp"])
    return by_commune


def _observation_block(
    rows: list[dict[str, Any]], tick_time: datetime
) -> dict[str, Any] | None:
    usable = [row for row in rows if row["timestamp"] <= tick_time]
    if not usable:
        return None
    latest = usable[-1]
    return {
        "source": "station_csv",
        "observed_at": latest["timestamp"].isoformat().replace("+00:00", "Z"),
        "quality": "fresh",  # engine downgrades by observed_at age itself
        "rain_1h_mm": _float(latest.get("rain_1h")),
        "rain_3h_mm": _accumulate(usable, tick_time, hours=3),
        "rain_6h_mm": _accumulate(usable, tick_time, hours=6),
        "rain_24h_mm": _accumulate(usable, tick_time, hours=24),
        "temp_c": _float(latest.get("temp")),
        "rh_pct": _float(latest.get("rh")),
        "wind_ms": _float(latest.get("wind")),
    }


def _accumulate(
    rows: list[dict[str, Any]], tick_time: datetime, hours: int
) -> float | None:
    """Sum of rain_1h over the window; None unless every hourly row is present."""
    window = [row for row in rows if row["timestamp"] > tick_time - timedelta(hours=hours)]
    values = [_float(row.get("rain_1h")) for row in window]
    if len(window) < hours or any(value is None for value in values):
        return None
    return round(sum(values), 2)


def _float(value: Any) -> float | None:
    if value is None or value == "":
        return None
    return float(value)
