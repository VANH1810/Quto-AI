from __future__ import annotations

from typing import Any

from risk_engine import CommuneState, evaluate

from test_validate import CFG, make_input


def _tick(
    rain_24h: float, tick: int, susceptibility: str = "high", **extra: Any
) -> dict[str, Any]:
    payload = make_input()
    payload["tick_id"] = f"2026-07-24T14:00:00Z#{tick:04d}"
    payload["commune"]["susceptibility"] = susceptibility
    payload["observations"]["rain_1h_mm"] = min(rain_24h, 5.0)
    payload["observations"]["rain_3h_mm"] = min(rain_24h, 15.0)
    payload["observations"]["rain_6h_mm"] = min(rain_24h, 30.0)
    payload["observations"]["rain_24h_mm"] = rain_24h
    payload["forecast"]["hourly"]["precip_mm"] = [0.0] * 72
    for key, value in extra.items():
        payload[key] = value
    return payload


def _event(outputs: list[Any], hazard: str) -> Any:
    return [item for item in outputs if item.hazard_type == hazard][0]


def test_raise_happens_immediately() -> None:
    outputs, state = evaluate(_tick(120.0, 1), CFG, CommuneState(commune_code="03136"))
    lu_quet = _event(outputs, "lu_quet_sat_lo")
    assert lu_quet.msg_type == "Alert"
    assert lu_quet.risk_level == 2
    assert state.active_hazards["lu_quet_sat_lo"].level == 2


def test_lower_requires_three_consecutive_ticks_and_no_rain_guard() -> None:
    state = CommuneState(commune_code="03136")
    _, state = evaluate(_tick(120.0, 1), CFG, state)
    for tick in (2, 3):
        outputs, state = evaluate(_tick(80.0, tick), CFG, state)
        assert _event(outputs, "lu_quet_sat_lo").risk_level == 2
        assert state.active_hazards["lu_quet_sat_lo"].clearing_count == tick - 1
    outputs, state = evaluate(_tick(80.0, 4), CFG, state)
    assert _event(outputs, "lu_quet_sat_lo").msg_type == "Cancel"
    assert "lu_quet_sat_lo" not in state.active_hazards


def test_next_six_hour_rain_guard_blocks_lowering() -> None:
    state = CommuneState(commune_code="03136")
    _, state = evaluate(_tick(120.0, 1), CFG, state)
    payload = _tick(80.0, 2)
    payload["forecast"]["hourly"]["precip_mm"][0] = 5.0
    outputs, state = evaluate(payload, CFG, state)
    assert _event(outputs, "lu_quet_sat_lo").risk_level == 2
    assert state.active_hazards["lu_quet_sat_lo"].clearing_count == 0


def test_no_active_level_three_to_idle_without_approval() -> None:
    state = CommuneState(commune_code="03136")
    _, state = evaluate(_tick(150.0, 1, susceptibility="very_high"), CFG, state)
    for tick in (2, 3, 4):
        outputs, state = evaluate(
            _tick(40.0, tick, susceptibility="very_high"), CFG, state
        )
    lu_quet = _event(outputs, "lu_quet_sat_lo")
    assert lu_quet.msg_type == "Update"
    assert lu_quet.data_quality["clear_recommended"] is True
    assert state.active_hazards["lu_quet_sat_lo"].level == 3


def test_level_three_clear_with_explicit_approval() -> None:
    state = CommuneState(commune_code="03136")
    _, state = evaluate(_tick(150.0, 1, susceptibility="very_high"), CFG, state)
    for tick in (2, 3):
        _, state = evaluate(_tick(40.0, tick, susceptibility="very_high"), CFG, state)
    payload = _tick(40.0, 4, susceptibility="very_high")
    payload["operator_actions"] = {"clear_approved_hazards": ["lu_quet_sat_lo"]}
    outputs, state = evaluate(payload, CFG, state)
    assert _event(outputs, "lu_quet_sat_lo").msg_type == "Cancel"
    assert "lu_quet_sat_lo" not in state.active_hazards


def test_same_level_retrigger_within_cooldown_is_marked_duplicate() -> None:
    state = CommuneState(commune_code="03136")
    _, state = evaluate(_tick(120.0, 1), CFG, state)
    first_emitted_at = state.active_hazards["lu_quet_sat_lo"].last_emitted_at
    outputs, state = evaluate(_tick(120.0, 2), CFG, state)
    duplicate = [
        item
        for item in _event(outputs, "lu_quet_sat_lo").modifiers
        if item["type"] == "cooldown_duplicate"
    ][0]
    assert duplicate["applied"] is True
    assert state.active_hazards["lu_quet_sat_lo"].last_emitted_at == first_emitted_at


def test_boundary_jitter_does_not_start_clearing() -> None:
    state = CommuneState(commune_code="03136")
    _, state = evaluate(_tick(101.0, 1), CFG, state)
    outputs, state = evaluate(_tick(99.0, 2), CFG, state)
    lu_quet = _event(outputs, "lu_quet_sat_lo")
    assert lu_quet.risk_level == 2
    assert state.active_hazards["lu_quet_sat_lo"].clearing_count == 0
