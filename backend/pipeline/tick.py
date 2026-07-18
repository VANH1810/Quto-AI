"""The get_tick seam: one TickData shape shared by live and synthetic sources."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Mapping

import numpy as np


@dataclass(frozen=True)
class PrescribedNowcast:
    """Scenario-supplied nowcast (bypasses the LSTM; live ticks carry grids)."""

    rain_6h_mm: float | None
    valid_fraction: float
    model_version: str = "scenario_prescribed"


@dataclass(frozen=True)
class TickData:
    tick_time: datetime  # aware UTC, top of hour
    seq: int
    source: str  # "live" | "scenario:<name>"
    synthetic: bool
    grids: dict[str, np.ndarray] | None  # live path into run_nowcast
    grid_info: Mapping[str, Any]  # substitutions, grid_mode, stats, calls, error
    nowcast_prescribed: Mapping[str, PrescribedNowcast] | None
    observations: Mapping[str, Mapping[str, Any] | None]  # by commune code
    forecast_blocks: Mapping[str, Mapping[str, Any] | None]  # by commune code
    antecedent_blocks: Mapping[str, Mapping[str, Any]]  # by commune code
    provenance: Mapping[str, Any]  # model_run, fetched_at, qm modes, fetch stats
    raw_paths: tuple[Path, ...] = field(default=())


def iso_z(moment: datetime) -> str:
    return moment.isoformat().replace("+00:00", "Z")
