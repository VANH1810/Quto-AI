"""Frozen commune registry: every payload-needed static field lives here."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Commune:
    code: str
    name: str
    lat: float
    lon: float
    elevation_m: float
    susceptibility: str
    region_qd18: int
    timezone: str = "Asia/Ho_Chi_Minh"
    susceptibility_source: str = "team_estimate_v1"  # VERIFY: OPEN-3, not official zoning


COMMUNES: tuple[Commune, ...] = (
    # VERIFY coords/code vs official post-2025-merger list (OPEN-4).
    Commune(code="03136", name="Mường Pồn", lat=21.46, lon=103.11,
            elevation_m=620, susceptibility="high", region_qd18=1),
    # VERIFY: code is a PLACEHOLDER in official format, not a confirmed commune code.
    Commune(code="03217", name="Tủa Chùa", lat=21.99, lon=103.35,
            elevation_m=1200, susceptibility="high", region_qd18=1),
    # VERIFY: code is a PLACEHOLDER in official format, not a confirmed commune code.
    Commune(code="03169", name="Mường Nhé", lat=22.18, lon=102.46,
            elevation_m=900, susceptibility="medium", region_qd18=1),
)

BY_CODE: dict[str, Commune] = {commune.code: commune for commune in COMMUNES}
assert len(BY_CODE) == len(COMMUNES), "commune codes must be unique"
