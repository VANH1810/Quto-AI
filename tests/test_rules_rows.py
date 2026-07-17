from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
import yaml

from risk_engine.rules import evaluate_table, load_thresholds

ROOT = Path(__file__).resolve().parents[1]
THRESHOLDS = ROOT / "config" / "thresholds.yaml"


def _rows() -> list[tuple[str, dict[str, Any]]]:
    data = yaml.safe_load(THRESHOLDS.read_text(encoding="utf-8"))
    return [
        (hazard, row) for hazard, rows in data["rule_tables"].items() for row in rows
    ]


def _base_values() -> dict[str, Any]:
    return {
        "eff_rain_24h": 0.0,
        "fcst_or_eff_rain_24h": 0.0,
        "fcst_rain_12h": 0.0,
        "rain_days_prior": 0,
        "susceptibility": "low",
        "nowcast_confidence": 0.0,
        "saturated": False,
        "forecast_heavy_rain_days": 0,
        "cold_episode_min_mean_c": 20.0,
        "cold_episode_duration_days": 0,
        "frost_risk": False,
        "fog_likely": False,
        "visibility_m": 50000.0,
    }


def _inside(bound: dict[str, Any]) -> Any:
    if "eq" in bound:
        return bound["eq"]
    if "in" in bound:
        return bound["in"][0]
    lo = bound.get("gte", bound.get("gt"))
    hi = bound.get("lte", bound.get("lt"))
    if lo is not None and hi is not None:
        return (float(lo) + float(hi)) / 2
    if lo is not None:
        return float(lo) + 1
    if hi is not None:
        return float(hi) - 1
    raise AssertionError(f"Unsupported bound {bound}")


def _outside(bound: dict[str, Any]) -> Any:
    if "eq" in bound:
        return not bound["eq"] if isinstance(bound["eq"], bool) else "__outside__"
    if "in" in bound:
        return "__outside__"
    if "gte" in bound:
        return float(bound["gte"]) - 0.1
    if "gt" in bound:
        return float(bound["gt"])
    if "lte" in bound:
        return float(bound["lte"]) + 0.1
    if "lt" in bound:
        return float(bound["lt"])
    raise AssertionError(f"Unsupported bound {bound}")


def _values_for(row: dict[str, Any]) -> dict[str, Any]:
    values = _base_values()
    for field, bound in row["bounds"].items():
        values[field] = _inside(bound)
    return values


@pytest.mark.parametrize(("hazard", "row"), _rows())
def test_each_yaml_row_matches_just_inside_bounds(
    hazard: str, row: dict[str, Any]
) -> None:
    thresholds = load_thresholds(THRESHOLDS)
    result = evaluate_table(thresholds, hazard, _values_for(row))
    matched_ids = {match.rule_id for match in result.matches}
    assert row["rule_id"] in matched_ids
    assert result.level >= row["level"]


@pytest.mark.parametrize(("hazard", "row"), _rows())
def test_each_yaml_row_rejects_just_outside_each_bound(
    hazard: str, row: dict[str, Any]
) -> None:
    thresholds = load_thresholds(THRESHOLDS)
    for field, bound in row["bounds"].items():
        values = _values_for(row)
        values[field] = _outside(bound)
        result = evaluate_table(thresholds, hazard, values)
        assert row["rule_id"] not in {match.rule_id for match in result.matches}


def test_article_46_region_1_legal_matrix_is_transcribed() -> None:
    data = yaml.safe_load(THRESHOLDS.read_text(encoding="utf-8"))
    rows = {row["rule_id"]: row for row in data["rule_tables"]["lu_quet_sat_lo"]}

    expected = {
        "qd18.art46.kv1.r1a": (1, False),
        "qd18.art46.kv1.r1b": (2, False),
        "qd18.art46.kv1.r1c": (3, False),
        "qd18.art46.kv1.r2a": (1, False),
        "qd18.art46.kv1.r2b": (2, False),
        "qd18.art46.kv1.r2c": (3, False),
        "qd18.art46.kv1.r3a": (2, False),
        "qd18.art46.kv1.r3b": (3, False),
        "qd18.art46.kv1.ex0a": (1, True),
        "qd18.art46.kv1.ex0b": (2, True),
        "qd18.art46.kv1.ex0c": (3, True),
        "qd18.art46.kv1.ex1a": (1, True),
        "qd18.art46.kv1.ex1b": (2, True),
        "qd18.art46.kv1.ex1c": (3, True),
        "qd18.art46.kv1.ex2a": (1, True),
        "qd18.art46.kv1.ex2b": (2, True),
        "qd18.art46.kv1.ex2c": (3, True),
        "qd18.art46.kv1.prewarning": (1, True),
    }
    assert set(rows) == set(expected)
    for rule_id, (level, extrapolated) in expected.items():
        assert rows[rule_id]["level"] == level
        assert rows[rule_id]["extrapolated"] is extrapolated


def test_all_rows_max_evaluation_ignores_yaml_order() -> None:
    thresholds = load_thresholds(THRESHOLDS)
    values = _base_values() | {
        "eff_rain_24h": 450.0,
        "fcst_or_eff_rain_24h": 450.0,
        "rain_days_prior": 3,
        "susceptibility": "high",
    }
    result = evaluate_table(thresholds, "lu_quet_sat_lo", values)
    assert result.level == 3
    assert "qd18.art46.kv1.r3b" in {match.rule_id for match in result.matches}


def test_ret_hai_is_capped_at_level_two_pending_legal_verification() -> None:
    thresholds = load_thresholds(THRESHOLDS)
    values = _base_values() | {
        "cold_episode_min_mean_c": 2.0,
        "cold_episode_duration_days": 12,
    }
    result = evaluate_table(thresholds, "ret_hai", values)
    assert result.level == 2
    assert all(match.level <= 2 for match in result.matches)
    assert {"pending_legal_verification"} <= {
        flag for match in result.matches for flag in match.flags
    }
