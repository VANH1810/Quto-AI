"""End-to-end acceptance tests for the pipeline (no real network; the live
path runs against a faked Open-Meteo transport with the real model + engine)."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

import pipeline.run as run_mod
from fetchers.openmeteo import OpenMeteoClient
from pipeline import scenarios


# ------------------------------------------------------------------ harness

@pytest.fixture
def cli(tmp_path, monkeypatch):
    """Redirect runs/, state/ and cache/ into tmp and return a CLI invoker."""
    monkeypatch.setattr(run_mod, "RUNS_DIR", tmp_path / "runs")
    monkeypatch.setattr(run_mod, "STATE_DIR", tmp_path / "state")
    monkeypatch.setattr(run_mod, "CACHE_DIR", tmp_path / "cache")

    def invoke(*argv: str) -> int:
        return run_mod.main(list(argv))

    invoke.runs_dir = tmp_path / "runs"
    invoke.state_dir = tmp_path / "state"
    return invoke


def _fake_http(start: datetime):
    """Fake Open-Meteo bodies aligned to the run's start hour."""
    def times(t0: datetime, hours: int) -> list[str]:
        return [(t0 + timedelta(hours=i)).strftime("%Y-%m-%dT%H:00")
                for i in range(hours)]

    def fake(self, params):
        count = len(params["latitude"].split(","))
        day0 = start.replace(hour=0)
        if "elevation" in params:  # point call
            t = times(day0 - timedelta(days=2), 240)
            return [{
                "elevation": 620,
                "hourly": {"time": t, "precipitation": [1.0] * len(t),
                           "temperature_2m": [22.0] * len(t),
                           "relative_humidity_2m": [90.0] * len(t),
                           "dew_point_2m": [19.0] * len(t),
                           "cloud_cover": [80.0] * len(t),
                           "wind_speed_10m": [2.0] * len(t)},
                "daily": {"time": [], "precipitation_sum": []},
            } for _ in range(count)]
        t = times(day0 - timedelta(days=1), 96)  # grid call
        return [{
            "hourly": {"time": t, "precipitation": [0.5] * len(t),
                       "cape": [500.0] * len(t),
                       "convective_inhibition": [None] * len(t),  # -> substitution
                       "lifted_index": [1.0] * len(t),
                       "temperature_850hPa": [18.0] * len(t),
                       "temperature_700hPa": [8.0] * len(t),
                       "temperature_500hPa": [-8.0] * len(t),
                       "relative_humidity_850hPa": [80.0] * len(t),
                       "relative_humidity_700hPa": [70.0] * len(t),
                       "relative_humidity_250hPa": [40.0] * len(t),
                       "wind_speed_850hPa": [5.0] * len(t),
                       "wind_direction_850hPa": [270.0] * len(t),
                       "wind_speed_250hPa": [20.0] * len(t),
                       "wind_direction_250hPa": [250.0] * len(t)},
        } for _ in range(count)]

    return fake


@pytest.fixture
def fake_live(monkeypatch):
    start = datetime.now(timezone.utc).replace(minute=0, second=0, microsecond=0)
    calls = {"n": 0}
    fake = _fake_http(start)

    def counting(self, params):
        calls["n"] += 1
        return fake(self, params)

    monkeypatch.setattr(OpenMeteoClient, "_http_get", counting)
    return calls


def _run_dir(cli) -> Path:
    return sorted(cli.runs_dir.iterdir())[-1]


def _assessments(run_dir: Path, tick_name: str) -> dict:
    return json.loads((run_dir / tick_name / "assessments.json").read_text())


def _hazard(data: dict, code: str, hazard: str) -> dict | None:
    for item in data["assessments"]:
        if item["commune_code"] == code and item["hazard_type"] == hazard:
            return item
    return None


# ----------------------------------------------------- acceptance 1: scenarios

def test_calm_heartbeats_only_zero_public_warnings(cli):
    assert cli("--source", "scenario", "--scenario", "calm") == 0
    run_dir = _run_dir(cli)
    for tick_dir in sorted(run_dir.glob("tick_*")):
        data = _assessments(run_dir, tick_dir.name)
        assert data["engine_errors"] == []
        for item in data["assessments"]:
            assert item["output_class"] == "heartbeat"
            assert item["risk_level"] == 0
            assert item["synthetic"] is True and item["status"] == "Exercise"


def test_storm_alert_escalation_hysteresis_no_auto_clear(cli):
    assert cli("--source", "scenario", "--scenario", "storm", "--ticks", "8") == 0
    run_dir = _run_dir(cli)
    lu = [
        _hazard(_assessments(run_dir, f"tick_{n:02d}"), "03136", "lu_quet_sat_lo")
        for n in range(1, 9)
    ]
    assert lu[0] is None and lu[1] is None  # calm ramp: heartbeats only
    assert lu[2]["msg_type"] == "Alert" and lu[2]["risk_level"] == 2
    assert lu[2]["output_class"] == "public_warning"
    # Escalation: Dieu 4 multi-hazard +1 (mua_lon L2 coincides) makes this L4.
    assert lu[3]["msg_type"] == "Update" and lu[3]["risk_level"] >= 3
    assert any(m["type"] == "multi_hazard_up1" and m["applied"]
               for m in lu[3]["modifiers"])
    for item in lu[4:]:  # taper: held, never Cancel, never below 3
        assert item["msg_type"] == "Update" and item["risk_level"] >= 3
    assert lu[7]["data_quality"].get("clear_recommended") is True
    assert lu[7]["requires_human_approval"] is True


def test_holey_nowcast_none_engine_holds_degraded(cli):
    assert cli("--source", "scenario", "--scenario", "holey", "--ticks", "6") == 0
    run_dir = _run_dir(cli)
    first = _hazard(_assessments(run_dir, "tick_01"), "03136", "lu_quet_sat_lo")
    assert first["msg_type"] == "Alert" and first["risk_level"] == 2
    for n in range(3, 7):  # the gap
        payload = json.loads(
            (run_dir / f"tick_{n:02d}" / "risk_input_03136.json").read_text()
        )
        assert payload["forecast"]["nowcast_rain_6h_mm"] is None  # None, NOT 0
        assert payload["observations"] is None
        held = _hazard(_assessments(run_dir, f"tick_{n:02d}"), "03136", "lu_quet_sat_lo")
        assert held["risk_level"] == 2 and held["msg_type"] != "Cancel"
        assert held["data_quality"]["degraded"] is True


# -------------------------------------------- acceptance 2/3/8: live (faked IO)

def test_live_ticks_provenance_and_cache(cli, fake_live, capsys):
    assert cli("--source", "live", "--ticks", "2") == 0
    out = capsys.readouterr().out
    assert "!! SCALER=DUMMY !!" in out
    assert fake_live["n"] == 5  # 1 point + 4 grid calls; tick 2 fully cache-served

    run_dir = _run_dir(cli)
    data = _assessments(run_dir, sorted(p.name for p in run_dir.glob("tick_*"))[0])
    assert data["engine_errors"] == []
    item = data["assessments"][0]
    prov = item["provenance"]
    for key in ("forecast_model_run", "points_fetched_at", "grid_fetched_at",
                "nowcast_model", "threshold_table_version",
                "threshold_table_sha256", "engine_version"):
        assert prov.get(key), f"missing provenance: {key}"
    assert prov["scaler"] == "dummy"
    assert {s["var"] for s in prov["substitutions"]} == {"CIN", "EWSS"}
    assert prov["qm"][item["commune_code"]] == "identity"
    assert prov["grid_mode"] == "stride2_nn"

    payload = json.loads(next(iter(run_dir.glob("tick_*/risk_input_03136.json"))).read_text())
    assert isinstance(payload["forecast"]["nowcast_rain_6h_mm"], float)  # real LSTM ran
    assert payload["forecast"]["nowcast_model"].endswith("+scaler=dummy")
    # antecedent visibly persisted: fake feed rains 24 mm/day
    history = json.loads((cli.state_dir / "antecedent" / "03136.json").read_text())
    assert history["daily_mm"]


# --------------------------------------------- acceptance 4: replay determinism

def test_replay_byte_identical_scenario(cli):
    assert cli("--source", "scenario", "--scenario", "storm", "--ticks", "3") == 0
    assert cli("--replay", str(_run_dir(cli))) == 0  # rc 1 on any byte mismatch


def test_replay_byte_identical_live(cli, fake_live):
    assert cli("--source", "live", "--ticks", "2") == 0
    live_dir = _run_dir(cli)
    assert cli("--replay", str(live_dir)) == 0
    replay_dir = _run_dir(cli)
    for tick_dir in live_dir.glob("tick_*"):
        original = (tick_dir / "assessments.json").read_bytes()
        assert (replay_dir / tick_dir.name / "assessments.json").read_bytes() == original


# ------------------------------------------------- acceptance 5: fault injection

def test_fault_grid_yields_nowcast_none_no_crash(cli, fake_live, monkeypatch):
    monkeypatch.setenv("EWS_FAKE_NET_FAIL", "grid")
    assert cli("--source", "live", "--ticks", "1") == 0
    run_dir = _run_dir(cli)
    tick = sorted(p.name for p in run_dir.glob("tick_*"))[0]
    data = _assessments(run_dir, tick)
    assert data["engine_errors"] == []
    payload = json.loads((run_dir / tick / "risk_input_03136.json").read_text())
    assert payload["forecast"]["nowcast_rain_6h_mm"] is None
    assert data["assessments"][0]["data_quality"]["degraded"] is True


def test_fault_points_yields_forecast_none_no_crash(cli, fake_live, monkeypatch):
    monkeypatch.setenv("EWS_FAKE_NET_FAIL", "points")
    assert cli("--source", "live", "--ticks", "1") == 0
    run_dir = _run_dir(cli)
    tick = sorted(p.name for p in run_dir.glob("tick_*"))[0]
    data = _assessments(run_dir, tick)
    assert data["engine_errors"] == []
    payload = json.loads((run_dir / tick / "risk_input_03136.json").read_text())
    assert payload["forecast"] is None
    assert data["assessments"][0]["data_quality"]["forecast"] == "missing"


# ------------------------------------------------------------- scenario shapes

def test_scenarios_exist_with_documented_lengths():
    assert scenarios.SCENARIO_TICKS == {"calm": 4, "storm": 8, "holey": 6}
