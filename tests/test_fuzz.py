from __future__ import annotations

import os
import random

import pytest

from risk_engine import CommuneState, evaluate

from test_validate import CFG, make_input


@pytest.mark.slow
def test_random_schema_valid_inputs_never_crash_or_emit_invalid_levels() -> None:
    count = 100_000 if os.getenv("RUN_RISK_ENGINE_SLOW") == "1" else 1_000
    rng = random.Random(20260724)
    for idx in range(count):
        payload = make_input()
        payload["tick_id"] = f"fuzz-{idx}"
        payload["commune"]["susceptibility"] = rng.choice(
            ["low", "medium", "high", "very_high"]
        )
        payload["antecedent"]["rain_days_prior"] = rng.randint(0, 5)
        payload["antecedent"]["api_mm"] = round(rng.uniform(0, 180), 2)
        payload["flags"] = {"synthetic": rng.choice([False, False, True])}
        _randomize_observations(payload, rng)
        _randomize_forecast(payload, rng)
        outputs, _ = evaluate(payload, CFG, CommuneState(commune_code="03136"))
        assert outputs
        for assessment in outputs:
            assert 0 <= assessment.risk_level <= 5
            assert assessment.cap_xml
            if assessment.synthetic:
                assert assessment.status == "Exercise"


def _randomize_observations(payload: dict, rng: random.Random) -> None:
    rain_1h = rng.uniform(0, 80)
    rain_3h = rain_1h + rng.uniform(0, 80)
    rain_6h = rain_3h + rng.uniform(0, 120)
    rain_24h = rain_6h + rng.uniform(0, 400)
    obs = payload["observations"]
    obs["rain_1h_mm"] = round(min(rain_1h, 250), 2)
    obs["rain_3h_mm"] = round(min(rain_3h, 500), 2)
    obs["rain_6h_mm"] = round(min(rain_6h, 750), 2)
    obs["rain_24h_mm"] = round(min(rain_24h, 1000), 2)
    obs["temp_c"] = round(rng.uniform(-5, 35), 2)
    obs["temp_min_24h_c"] = round(min(obs["temp_c"], rng.uniform(-8, 30)), 2)
    obs["rh_pct"] = round(rng.uniform(40, 100), 2)
    obs["wind_ms"] = round(rng.uniform(0, 20), 2)
    obs["dewpoint_c"] = round(obs["temp_c"] - rng.uniform(0, 6), 2)
    obs["visibility_m"] = rng.choice([None, round(rng.uniform(100, 50000), 2)])


def _randomize_forecast(payload: dict, rng: random.Random) -> None:
    forecast = payload["forecast"]
    forecast["hourly"]["precip_mm"] = [round(rng.uniform(0, 30), 2) for _ in range(72)]
    forecast["hourly"]["temp_c"] = [round(rng.uniform(-5, 35), 2) for _ in range(72)]
    forecast["hourly"]["cloud_cover_pct"] = [
        round(rng.uniform(0, 100), 2) for _ in range(72)
    ]
    forecast["hourly"]["wind_ms"] = [round(rng.uniform(0, 20), 2) for _ in range(72)]
    forecast["hourly"]["rh_pct"] = [round(rng.uniform(40, 100), 2) for _ in range(72)]
    forecast["nowcast_rain_6h_mm"] = round(rng.uniform(0, 300), 2)
    forecast["nowcast_confidence"] = round(rng.uniform(0, 1), 2)
