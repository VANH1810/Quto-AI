from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import pytest

import risk_engine.engine as engine_module
from risk_engine import (
    CommuneState,
    EngineError,
    HazardState,
    RiskEngineInput,
    evaluate,
    load_thresholds,
)
from risk_engine.derive import derive
from risk_engine.output import OutputValidationError, _urgency, _validate_output
from risk_engine.rules import ConfigIntegrityError
from risk_engine.schemas import HazardAssessment, assessment_to_dict
from risk_engine.temporal import _jitter_allows_drop, _within_cooldown
from risk_engine.validate import ValidationError, parse_utc, validate_input

ROOT = Path(__file__).resolve().parents[1]
CFG = load_thresholds(ROOT / "config" / "thresholds.yaml")


def make_input(**overrides: Any) -> dict[str, Any]:
    start = datetime(2026, 7, 24, 14, tzinfo=timezone.utc)
    hours = [
        (start + timedelta(hours=i)).isoformat().replace("+00:00", "Z")
        for i in range(72)
    ]
    payload: dict[str, Any] = {
        "schema_version": "1.0",
        "tick_id": "2026-07-24T14:00:00Z#0042",
        "evaluated_at": "2026-07-24T14:00:00Z",
        "commune": {
            "code": "03136",
            "name": "Muong Pon",
            "region_qd18": 1,
            "susceptibility": "high",
            "susceptibility_source": "static_map_v2",
            "elevation_mean_m": 620,
            "timezone": "Asia/Ho_Chi_Minh",
        },
        "observations": {
            "source": "station_48811_dien_bien",
            "observed_at": "2026-07-24T13:00:00Z",
            "quality": "fresh",
            "rain_1h_mm": 10.0,
            "rain_3h_mm": 20.0,
            "rain_6h_mm": 30.0,
            "rain_24h_mm": 40.0,
            "temp_c": 22.0,
            "temp_min_24h_c": 20.0,
            "rh_pct": 90.0,
            "wind_ms": 2.0,
            "dewpoint_c": 20.0,
            "visibility_m": None,
        },
        "forecast": {
            "source": "open_meteo_best_match+downscale_v1",
            "issued_at": "2026-07-24T12:00:00Z",
            "model_run": "ecmwf_ifs025_2026072406",
            "hourly": {
                "time": hours,
                "precip_mm": [0.0] * 72,
                "temp_c": [22.0] * 72,
                "cloud_cover_pct": [90.0] * 72,
                "wind_ms": [2.0] * 72,
                "rh_pct": [90.0] * 72,
            },
            "nowcast_rain_6h_mm": 0.0,
            "nowcast_model": "xgb_dienbien_v3",
            "nowcast_confidence": 0.7,
        },
        "antecedent": {
            "rain_days_prior": 2,
            "rain_day_threshold_mm": 16.0,
            "api_mm": 88.0,
            "days_since_data_gap": 14,
        },
        "config_ref": {
            "threshold_table_version": CFG.version,
            "threshold_table_sha256": CFG.sha256,
        },
    }
    for key, value in overrides.items():
        payload[key] = value
    return payload


def test_schema_rejects_extra_properties() -> None:
    payload = make_input(extra=True)
    with pytest.raises(ValidationError):
        validate_input(payload, CFG)


def test_out_of_range_rain_is_missing_not_clamped() -> None:
    payload = make_input()
    payload["observations"]["rain_24h_mm"] = 9999.0
    validated = validate_input(payload, CFG)
    assert validated.payload["observations"]["rain_24h_mm"] is None
    assert "rain_24h_mm" in validated.data_quality["missing_fields"]


def test_missing_observation_field_cannot_lower_active_level() -> None:
    payload = make_input()
    payload["observations"]["rain_24h_mm"] = 9999.0
    state = CommuneState(
        commune_code="03136",
        active_hazards={
            "lu_quet_sat_lo": HazardState(
                status="ACTIVE",
                level=2,
                active_since="2026-07-24T12:00:00Z",
                last_emitted_at="2026-07-24T12:00:00Z",
                last_emitted_level=2,
                driving_threshold=100.0,
            )
        },
    )
    outputs, new_state = evaluate(payload, CFG, state)
    lu_quet = [item for item in outputs if item.hazard_type == "lu_quet_sat_lo"][0]
    assert lu_quet.risk_level == 2
    assert new_state.active_hazards["lu_quet_sat_lo"].level == 2


def test_internal_consistency_marks_observations_suspect_and_weights_forecast() -> None:
    payload = make_input()
    payload["observations"]["rain_1h_mm"] = 50.0
    payload["observations"]["rain_3h_mm"] = 20.0
    payload["forecast"]["hourly"]["precip_mm"] = [5.0] * 72
    validated = validate_input(payload, CFG)
    derived = derive(validated, CommuneState(commune_code="03136"), CFG)
    assert validated.data_quality["observations"] == "suspect"
    assert derived.values["eff_rain_source"] == "nwp_24h"


def test_stale_observations_older_than_six_hours_become_missing() -> None:
    payload = make_input()
    payload["observations"]["observed_at"] = "2026-07-24T07:00:00Z"
    validated = validate_input(payload, CFG)
    assert validated.payload["observations"] is None
    assert validated.data_quality["observations"] == "missing"


def test_non_monotonic_forecast_time_rejects_forecast_block() -> None:
    payload = make_input()
    payload["forecast"]["hourly"]["time"][1] = payload["forecast"]["hourly"]["time"][0]
    validated = validate_input(payload, CFG)
    assert validated.payload["forecast"] is None
    assert validated.data_quality["forecast"] == "missing"


def test_engine_refuses_config_hash_mismatch() -> None:
    payload = make_input()
    payload["config_ref"]["threshold_table_sha256"] = "bad"
    with pytest.raises(ConfigIntegrityError):
        evaluate(payload, CFG, CommuneState(commune_code="03136"))


def test_load_thresholds_refuses_expected_sha_mismatch() -> None:
    with pytest.raises(ConfigIntegrityError):
        load_thresholds(ROOT / "config" / "thresholds.yaml", expected_sha256="bad")


def test_demo_isolation_propagates_to_output_and_cap_xml() -> None:
    payload = make_input(flags={"synthetic": True, "exercise": True})
    payload["observations"]["rain_24h_mm"] = 120.0
    outputs, _ = evaluate(payload, CFG, CommuneState(commune_code="03136"))
    lu_quet = [item for item in outputs if item.hazard_type == "lu_quet_sat_lo"][0]
    assert lu_quet.status == "Exercise"
    assert lu_quet.synthetic is True
    assert "<status>Exercise</status>" in lu_quet.cap_xml
    assert "<value>true</value>" in lu_quet.cap_xml


def test_output_carries_trace_quality_and_provenance() -> None:
    payload = make_input()
    payload["observations"]["rain_24h_mm"] = 120.0
    outputs, _ = evaluate(payload, CFG, CommuneState(commune_code="03136"))
    lu_quet = [item for item in outputs if item.hazard_type == "lu_quet_sat_lo"][0]
    assert lu_quet.triggered_rules
    assert "eff_rain_24h" in lu_quet.derived
    assert "degraded" in lu_quet.data_quality
    assert lu_quet.provenance["threshold_table_sha256"] == CFG.sha256


def test_internal_error_is_fail_stop_engine_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def explode(*args: object, **kwargs: object) -> object:
        raise RuntimeError("boom")

    monkeypatch.setattr(engine_module, "evaluate_all", explode)
    with pytest.raises(EngineError) as exc_info:
        evaluate(make_input(), CFG, CommuneState(commune_code="03136"))
    assert exc_info.value.commune_code == "03136"
    assert exc_info.value.partial_trace


def test_naive_timestamp_is_rejected() -> None:
    with pytest.raises(ValidationError):
        parse_utc("2026-07-24T14:00:00")


def test_nullable_input_blocks_are_marked_missing() -> None:
    payload = make_input(observations=None, forecast=None)
    validated = validate_input(payload, CFG)
    assert validated.data_quality["observations"] == "missing"
    assert validated.data_quality["forecast"] == "missing"


def test_observations_between_two_and_six_hours_are_stale() -> None:
    payload = make_input()
    payload["observations"]["observed_at"] = "2026-07-24T11:30:00Z"
    validated = validate_input(payload, CFG)
    assert validated.payload["observations"]["quality"] == "stale"
    assert validated.data_quality["observations"] == "stale"


def test_forecast_stale_aligned_physical_and_nowcast_paths() -> None:
    stale = make_input()
    stale["forecast"]["issued_at"] = "2026-07-24T04:00:00Z"
    assert validate_input(stale, CFG).data_quality["forecast"] == "stale"

    unaligned = make_input()
    unaligned["forecast"]["hourly"]["precip_mm"].pop()
    assert validate_input(unaligned, CFG).payload["forecast"] is None

    early = make_input()
    start = datetime(2026, 7, 24, 12, tzinfo=timezone.utc)
    early["forecast"]["hourly"]["time"] = [
        (start + timedelta(hours=i)).isoformat().replace("+00:00", "Z")
        for i in range(72)
    ]
    assert validate_input(early, CFG).payload["forecast"] is None

    invalid_precip = make_input()
    invalid_precip["forecast"]["hourly"]["precip_mm"][0] = 999.0
    assert validate_input(invalid_precip, CFG).payload["forecast"] is None

    invalid_nowcast = make_input()
    invalid_nowcast["forecast"]["nowcast_rain_6h_mm"] = 9999.0
    validated = validate_input(invalid_nowcast, CFG)
    assert validated.payload["forecast"]["nowcast_rain_6h_mm"] is None


def test_antecedent_gap_and_invalid_api_are_degraded() -> None:
    payload = make_input()
    payload["antecedent"]["api_mm"] = -1.0
    payload["antecedent"]["days_since_data_gap"] = 0
    validated = validate_input(payload, CFG)
    assert validated.payload["antecedent"]["api_mm"] is None
    assert "antecedent_history" in validated.data_quality["suspect_fields"]


def test_derive_missing_forecast_cold_frost_and_fog_edges() -> None:
    no_forecast = validate_input(make_input(forecast=None), CFG)
    missing = derive(no_forecast, CommuneState(commune_code="03136"), CFG)
    assert missing.values["eff_rain_source"] == "observed_24h"
    assert missing.values["forecast_heavy_rain_days"] == 0

    payload = make_input()
    payload["forecast"]["nowcast_confidence"] = None
    payload["forecast"]["hourly"]["temp_c"] = [3.0] * 72
    payload["forecast"]["hourly"]["temp_c"][0] = None
    payload["forecast"]["hourly"]["cloud_cover_pct"] = [10.0] * 72
    payload["forecast"]["hourly"]["wind_ms"] = [1.0] * 72
    payload["observations"]["observed_at"] = "2026-07-24T15:00:00Z"
    payload["observations"]["visibility_m"] = 500.0
    derived = derive(
        validate_input(payload, CFG), CommuneState(commune_code="03136"), CFG
    )
    assert derived.values["nowcast_confidence"] == 0.0
    assert derived.values["cold_episode_duration_days"] >= 1
    assert derived.values["frost_risk"] is True
    assert derived.values["fog_likely"] is True
    assert derived.values["visibility_m"] == 500.0


def test_fog_proxy_without_visibility_sensor() -> None:
    payload = make_input()
    payload["observations"]["observed_at"] = "2026-07-24T16:00:00Z"
    payload["observations"]["rh_pct"] = 99.0
    payload["observations"]["wind_ms"] = 1.0
    payload["observations"]["temp_c"] = 20.0
    payload["observations"]["temp_min_24h_c"] = 19.0
    payload["observations"]["dewpoint_c"] = 19.2
    payload["observations"]["visibility_m"] = None
    derived = derive(
        validate_input(payload, CFG), CommuneState(commune_code="03136"), CFG
    )
    assert derived.values["fog_likely"] is True


def test_idempotency_conflict_version_and_state_mismatch_reject() -> None:
    payload = make_input()
    _, state = evaluate(payload, CFG, CommuneState(commune_code="03136"))
    changed = make_input()
    changed["observations"]["rain_24h_mm"] = 120.0
    with pytest.raises(ValidationError):
        evaluate(changed, CFG, state)

    bad_version = make_input()
    bad_version["config_ref"]["threshold_table_version"] = "bad"
    with pytest.raises(ConfigIntegrityError):
        evaluate(bad_version, CFG, CommuneState(commune_code="03136"))

    with pytest.raises(ValidationError):
        evaluate(make_input(), CFG, CommuneState(commune_code="other"))

    outputs, _ = evaluate(
        RiskEngineInput(make_input()), CFG, CommuneState(commune_code="03136")
    )
    assert outputs


def test_temporal_raise_non_suppressed_same_level_and_private_edges() -> None:
    state = CommuneState(
        commune_code="03136",
        active_hazards={
            "lu_quet_sat_lo": HazardState(
                status="ACTIVE",
                level=1,
                driving_threshold=80.0,
                last_emitted_at="2026-07-24T00:00:00Z",
            )
        },
    )
    payload = make_input()
    payload["observations"]["rain_24h_mm"] = 120.0
    outputs, state = evaluate(payload, CFG, state)
    assert [item for item in outputs if item.hazard_type == "lu_quet_sat_lo"][
        0
    ].msg_type == "Update"
    assert state.active_hazards["lu_quet_sat_lo"].level == 2

    same_level_state = CommuneState(
        commune_code="03136",
        active_hazards={
            "lu_quet_sat_lo": HazardState(
                status="ACTIVE",
                level=2,
                driving_threshold=100.0,
                last_emitted_at="2026-07-24T00:00:00Z",
            )
        },
    )
    outputs, _ = evaluate(
        payload | {"tick_id": "same-level-late"}, CFG, same_level_state
    )
    lu_quet = [item for item in outputs if item.hazard_type == "lu_quet_sat_lo"][0]
    duplicate = [
        item for item in lu_quet.modifiers if item["type"] == "cooldown_duplicate"
    ][0]
    assert duplicate["applied"] is False
    assert _jitter_allows_drop(
        HazardState(driving_threshold=None), {"eff_rain_24h": None}
    )
    assert _within_cooldown(None, "2026-07-24T14:00:00Z", 6) is False


def test_output_validation_and_urgency_edges() -> None:
    outputs, _ = evaluate(make_input(), CFG, CommuneState(commune_code="03136"))
    base = outputs[0]
    invalid_level = HazardAssessment(**(assessment_to_dict(base) | {"risk_level": 9}))
    with pytest.raises(OutputValidationError):
        _validate_output(invalid_level)

    public_without_rule = HazardAssessment(
        **(
            assessment_to_dict(base)
            | {"output_class": "public_warning", "triggered_rules": []}
        )
    )
    with pytest.raises(OutputValidationError):
        _validate_output(public_without_rule)

    assert _urgency("2026-07-24T22:00:00Z", "2026-07-24T14:00:00Z") == "Expected"
    assert _urgency("2026-07-26T14:00:00Z", "2026-07-24T14:00:00Z") == "Future"
