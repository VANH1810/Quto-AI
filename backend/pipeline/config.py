"""Static paths and pipeline-owned constants (nothing here overrides the engine)."""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
THRESHOLDS_PATH = REPO_ROOT / "config" / "thresholds.yaml"
NOWCAST_ARTIFACTS = REPO_ROOT / "backend" / "nowcast" / "artifacts"
MASKS_PATH = NOWCAST_ARTIFACTS / "commune_masks.npz"
SCALER_PATH = NOWCAST_ARTIFACTS / "scaler.json"
CACHE_DIR = REPO_ROOT / "cache" / "openmeteo"
STATE_DIR = REPO_ROOT / "state"
RUNS_DIR = REPO_ROOT / "runs"
QM_DIR = REPO_ROOT / "backend" / "downscale" / "artifacts"

# Prior belief in the nowcast model's skill; multiplied by the tick's
# valid_fraction to form nowcast_confidence. 0.6 is exactly the engine's G7
# gate when coverage is full — a deliberate "trusted only at full coverage"
# stance until the rung-4 retrain replaces the DUMMY scaler.
NOWCAST_SKILL_PRIOR = 0.6
FORECAST_SOURCE = "open_meteo_best_match+qm_v1"
MASKS_VERSION = "provisional_circles_v1"
