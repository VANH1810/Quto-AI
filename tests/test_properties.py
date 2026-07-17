from __future__ import annotations

import json

from hypothesis import given, settings
from hypothesis import strategies as st

from risk_engine import CommuneState, HazardState, evaluate
from risk_engine.rules import HazardRuleResult, apply_multi_hazard, evaluate_table
from risk_engine.schemas import assessment_to_dict

from test_validate import CFG, make_input


def _values(rain: float, susceptibility: str, days: int) -> dict[str, object]:
    return {
        "eff_rain_24h": rain,
        "eff_rain_source": "observed_24h",
        "independent_rain_24h": rain,
        "fcst_or_eff_rain_24h": rain,
        "fcst_rain_12h": rain / 2,
        "rain_days_prior": days,
        "susceptibility": susceptibility,
        "nowcast_confidence": 0.7,
        "saturated": days >= 2,
        "forecast_heavy_rain_days": days,
        "cold_episode_min_mean_c": 20.0,
        "cold_episode_duration_days": 0,
        "frost_risk": False,
        "fog_likely": False,
        "visibility_m": 50000.0,
    }


@given(
    low=st.floats(min_value=0, max_value=600, allow_nan=False, allow_infinity=False),
    delta=st.floats(min_value=0, max_value=600, allow_nan=False, allow_infinity=False),
    days=st.integers(min_value=0, max_value=5),
    susceptibility=st.sampled_from(["low", "medium", "high", "very_high"]),
)
@settings(max_examples=150)
def test_more_rain_never_yields_lower_lu_quet_level(
    low: float,
    delta: float,
    days: int,
    susceptibility: str,
) -> None:
    high = min(1000.0, low + delta)
    first = evaluate_table(
        CFG, "lu_quet_sat_lo", _values(low, susceptibility, days)
    ).level
    second = evaluate_table(
        CFG, "lu_quet_sat_lo", _values(high, susceptibility, days)
    ).level
    assert second >= first


@given(
    rain=st.floats(min_value=0, max_value=600, allow_nan=False, allow_infinity=False),
    days=st.integers(min_value=0, max_value=5),
)
@settings(max_examples=150)
def test_higher_susceptibility_never_yields_lower_level(rain: float, days: int) -> None:
    levels = [
        evaluate_table(CFG, "lu_quet_sat_lo", _values(rain, susc, days)).level
        for susc in ["low", "medium", "high", "very_high"]
    ]
    assert levels == sorted(levels)


def test_adding_coincident_hazard_never_lowers_combined_level() -> None:
    base = {
        "lu_quet_sat_lo": HazardRuleResult("lu_quet_sat_lo", 2, (), "public_warning"),
        "mua_lon": HazardRuleResult("mua_lon", 0, (), "heartbeat"),
    }
    combined = {
        "lu_quet_sat_lo": HazardRuleResult("lu_quet_sat_lo", 2, (), "public_warning"),
        "mua_lon": HazardRuleResult("mua_lon", 2, (), "public_warning"),
    }
    assert (
        apply_multi_hazard(combined)["lu_quet_sat_lo"].level
        >= apply_multi_hazard(base)["lu_quet_sat_lo"].level
    )


def test_missing_data_never_lowers_active_level() -> None:
    state = CommuneState(
        commune_code="03136",
        active_hazards={
            "lu_quet_sat_lo": HazardState(
                status="ACTIVE", level=2, driving_threshold=100.0
            )
        },
    )
    present = make_input()
    present["tick_id"] = "present"
    present["observations"]["rain_24h_mm"] = 40.0
    missing = make_input()
    missing["tick_id"] = "missing"
    missing["observations"]["rain_24h_mm"] = 9999.0
    present_outputs, _ = evaluate(present, CFG, state)
    missing_outputs, _ = evaluate(missing, CFG, state)
    present_level = [
        item for item in present_outputs if item.hazard_type == "lu_quet_sat_lo"
    ][0].risk_level
    missing_level = [
        item for item in missing_outputs if item.hazard_type == "lu_quet_sat_lo"
    ][0].risk_level
    assert missing_level >= present_level


def test_same_tick_same_payload_is_idempotent() -> None:
    payload = make_input()
    outputs, state = evaluate(payload, CFG, CommuneState(commune_code="03136"))
    replay_outputs, replay_state = evaluate(payload, CFG, state)
    assert _stable_json(replay_outputs) == _stable_json(outputs)
    assert replay_state == state


def test_state_machine_has_no_level_three_auto_clear_path_without_approval() -> None:
    state = CommuneState(
        commune_code="03136",
        active_hazards={
            "lu_quet_sat_lo": HazardState(
                status="ACTIVE", level=3, driving_threshold=100.0
            )
        },
    )
    for idx in range(3):
        payload = make_input()
        payload["tick_id"] = f"no-clear-{idx}"
        payload["observations"]["rain_24h_mm"] = 20.0
        outputs, state = evaluate(payload, CFG, state)
    lu_quet = [item for item in outputs if item.hazard_type == "lu_quet_sat_lo"][0]
    assert lu_quet.msg_type != "Cancel"
    assert state.active_hazards["lu_quet_sat_lo"].level == 3


def test_boundary_jitter_99_101_has_at_most_one_transition_in_cooldown_window() -> None:
    state = CommuneState(commune_code="03136")
    emitted = []
    for idx, rain in enumerate([101.0, 99.0, 101.0, 99.0], start=1):
        payload = make_input()
        payload["tick_id"] = f"jitter-{idx}"
        payload["observations"]["rain_24h_mm"] = rain
        payload["observations"]["rain_6h_mm"] = min(rain, 30.0)
        outputs, state = evaluate(payload, CFG, state)
        emitted.extend(
            item.msg_type for item in outputs if item.hazard_type == "lu_quet_sat_lo"
        )
    assert emitted.count("Alert") <= 1
    assert "Cancel" not in emitted


def _stable_json(outputs: list[object]) -> str:
    return json.dumps([assessment_to_dict(item) for item in outputs], sort_keys=True)
