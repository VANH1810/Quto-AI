"""Unit tests for the new pipeline/fetcher/downscale layers (no network)."""

from __future__ import annotations

import json
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import numpy as np
import pytest

from downscale.quantile_map import apply_qm
from fetchers import station
from fetchers.openmeteo import (
    cache_key,
    k_index,
    load_scaler_meta,
    magnus_dewpoint_c,
    stride2_latlons,
    wind_uv,
)
from nowcast.grid_constants import GRID_SHAPE
from pipeline import antecedent, state_store
from pipeline.config import SCALER_PATH
from pipeline.run import _resolve_exercise
from risk_engine import CommuneState
from risk_engine.schemas import HazardState


# ---------------------------------------------------------------- wind and KX

def test_wind_uv_known_angles():
    u, v = wind_uv(np.array(10.0), np.array(270.0))  # westerly: from the west
    assert u == pytest.approx(10.0)
    assert v == pytest.approx(0.0, abs=1e-9)
    u, v = wind_uv(np.array(5.0), np.array(0.0))  # northerly: from the north
    assert u == pytest.approx(0.0, abs=1e-9)
    assert v == pytest.approx(-5.0)
    u, v = wind_uv(np.array(8.0), np.array(90.0))  # easterly
    assert u == pytest.approx(-8.0)


def test_magnus_dewpoint_hand_computed():
    # RH=100% must return the temperature itself; 20C/50% ~ 9.26C (textbook value)
    assert magnus_dewpoint_c(np.array(20.0), np.array(100.0)) == pytest.approx(20.0)
    assert magnus_dewpoint_c(np.array(20.0), np.array(50.0)) == pytest.approx(9.26, abs=0.05)


def test_k_index_hand_computed():
    # Saturated at 850/700: KX = (T850-T500) + Td850 - (T700-Td700) = 30 + 20 - 0
    kx = k_index(np.array(20.0), np.array(10.0), np.array(-10.0),
                 np.array(100.0), np.array(100.0))
    assert kx == pytest.approx(50.0, abs=1e-6)


# ------------------------------------------------------------------ stride-2

def test_stride2_covers_grid():
    lats, lons, sub_shape = stride2_latlons()
    assert sub_shape == ((GRID_SHAPE[0] + 1) // 2, (GRID_SHAPE[1] + 1) // 2)
    assert len(lats) == len(lons) == sub_shape[0] * sub_shape[1] == 380
    assert max(lats) == pytest.approx(22.58) and min(lons) == pytest.approx(102.12)


# ------------------------------------------------------------------ cache key

def test_cache_key_stability_and_hour_bucket():
    a = cache_key("http://x", {"b": "2", "a": "1"}, "2026-07-18T07")
    b = cache_key("http://x", {"a": "1", "b": "2"}, "2026-07-18T07")
    c = cache_key("http://x", {"a": "1", "b": "2"}, "2026-07-18T08")
    assert a == b != c


# -------------------------------------------------------------------- scaler

def test_scaler_meta_flags_dummy_and_z0_substitution():
    means, status = load_scaler_meta(SCALER_PATH)
    assert status == "dummy"  # replace scaler -> this test documents the flip
    payload = json.loads(SCALER_PATH.read_text())
    scale = dict(zip(payload["feature_order"], payload["scale"]))
    for var in ("EWSS", "CIN"):
        z = (means[var] - means[var]) / scale[var]
        assert z == 0.0  # training-mean substitution standardizes to exactly 0


# ------------------------------------------------------------------------ QM

def test_qm_identity_without_artifact(tmp_path):
    times = [f"2026-07-18T{h:02d}:00Z" for h in range(24)]
    precip = [1.0] * 24
    corrected, mode = apply_qm("03136", times, precip, tmp_path)
    assert mode == "identity" and corrected == precip


def test_qm_fitted_doubles_daily_totals(tmp_path):
    quantiles = [float(q) for q in range(0, 105, 5)]
    (tmp_path / "qm_03136.json").write_text(json.dumps({
        "quantiles_forecast": quantiles,
        "quantiles_truth": [q * 2 for q in quantiles],
    }))
    times = [f"2026-07-18T{h:02d}:00Z" for h in range(24)]
    corrected, mode = apply_qm("03136", times, [0.5] * 24, tmp_path)
    assert mode == "qm_v1"
    assert sum(corrected) == pytest.approx(24.0)  # 12 mm/day mapped to 24 mm


# ------------------------------------------------------------------ antecedent

def test_daily_totals_local_day_boundary_rollover():
    # UTC 17:00 is midnight in Asia/Ho_Chi_Minh: 24 hours from 07-16T17:00Z
    # form exactly local day 2026-07-17.
    start = datetime(2026, 7, 16, 17, tzinfo=timezone.utc)
    times = [(start + timedelta(hours=i)).isoformat().replace("+00:00", "Z")
             for i in range(24)]
    totals = antecedent.daily_totals_from_hourly(times, [1.0] * 24, "Asia/Ho_Chi_Minh")
    assert totals == {"2026-07-17": 24.0}
    # a missing hour makes the day a gap, never a low-balled total
    totals = antecedent.daily_totals_from_hourly(times[:23], [1.0] * 23, "Asia/Ho_Chi_Minh")
    assert totals == {}


def test_compute_block_rain_days_api_and_gap():
    today = date(2026, 7, 18)
    daily = {"2026-07-14": 2.0, "2026-07-15": 20.0, "2026-07-16": 30.0,
             "2026-07-17": 18.0}
    block = antecedent.compute_block(daily, today, 16.0)
    assert block["rain_days_prior"] == 3  # 15,16,17 all >= 16 mm
    expected_api = ((2.0 * 0.85 + 20.0) * 0.85 + 30.0) * 0.85 + 18.0
    assert block["api_mm"] == pytest.approx(expected_api, abs=0.01)
    assert block["days_since_data_gap"] == 4
    holey = {"2026-07-15": 20.0, "2026-07-17": 18.0}  # 16th missing
    assert antecedent.compute_block(holey, today, 16.0)["days_since_data_gap"] == 1


# --------------------------------------------------------------------- station

def test_station_mode_none_returns_none_blocks():
    now = datetime(2026, 7, 18, 7, tzinfo=timezone.utc)
    blocks = station.load_observations("none", None, ["03136"], now)
    assert blocks == {"03136": None}


def test_station_csv_accumulations(tmp_path):
    now = datetime(2026, 7, 18, 7, tzinfo=timezone.utc)
    rows = ["timestamp,commune_code,rain_1h,temp,rh,wind"]
    for hour in range(5, 8):
        rows.append(f"2026-07-18T{hour:02d}:00:00Z,03136,2.0,22.0,90,1.5")
    csv_path = tmp_path / "station.csv"
    csv_path.write_text("\n".join(rows))
    block = station.load_observations("csv", csv_path, ["03136"], now)["03136"]
    assert block["rain_1h_mm"] == 2.0
    assert block["rain_3h_mm"] == 6.0
    assert block["rain_6h_mm"] is None  # incomplete window -> None, not a sum


# ----------------------------------------------------------------- state store

def test_commune_state_roundtrip():
    state = CommuneState(
        commune_code="03136",
        active_hazards={"lu_quet_sat_lo": HazardState(status="ACTIVE", level=3,
                                                      active_since="2026-07-18T07:00:00Z")},
    )
    data = state_store.state_to_json(state)
    rebuilt = state_store.state_from_json(data)
    assert state_store.state_to_json(rebuilt) == data
    assert rebuilt.active_hazards["lu_quet_sat_lo"].level == 3


def test_tick_counter_monotonic(tmp_path):
    assert state_store.next_tick_seq(tmp_path) == 1
    state_store.save_tick_seq(tmp_path, 7)
    assert state_store.next_tick_seq(tmp_path) == 7


# --------------------------------------------------------------- exercise gate

def test_actual_requires_double_gate(monkeypatch):
    assert _resolve_exercise(False) is True
    monkeypatch.delenv("EWS_ALLOW_ACTUAL", raising=False)
    with pytest.raises(SystemExit):
        _resolve_exercise(True)
    monkeypatch.setenv("EWS_ALLOW_ACTUAL", "1")
    assert _resolve_exercise(True) is False


# ------------------------------------------------------------ provisional masks

def test_provisional_masks_metadata(tmp_path):
    import sys

    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend" / "scripts"))
    from build_commune_masks import build_provisional_circle_masks

    out = tmp_path / "masks.npz"
    build_provisional_circle_masks(out, radius_km=6.0)
    from nowcast.aggregate import load_masks

    masks = load_masks(out)
    assert set(masks.masks) == {"03136", "03217", "03169"}
    assert all(m.shape == GRID_SHAPE and m.any() for m in masks.masks.values())
