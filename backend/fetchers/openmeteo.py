"""Open-Meteo client: batched commune point forecasts + stride-2 nowcast grids.

Politeness rules are structural: one batched point call, grid chunks of <=100
locations spaced 0.5 s apart, sha256 disk cache keyed per UTC hour, and a
replay transport that never touches the network.
"""

from __future__ import annotations

import json
import math
import os
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
from typing import Any, Iterable, Mapping

import numpy as np
import requests

from nowcast.grid_constants import DLAT, DLON, GRID_SHAPE, LAT0, LON0

FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
POINT_HOURLY = (
    "precipitation,temperature_2m,relative_humidity_2m,dew_point_2m,"
    "cloud_cover,wind_speed_10m"
)
POINT_DAILY = "precipitation_sum,temperature_2m_min,temperature_2m_max"
GRID_HOURLY = (
    "precipitation,cape,convective_inhibition,lifted_index,"
    "temperature_850hPa,temperature_700hPa,temperature_500hPa,"
    "relative_humidity_850hPa,relative_humidity_700hPa,relative_humidity_250hPa,"
    "wind_speed_850hPa,wind_direction_850hPa,"
    "wind_speed_250hPa,wind_direction_250hPa"
)
GRID_CHUNK_SIZE = 100
GRID_CALL_SPACING_S = 0.5
RETRY_BACKOFF_S = (1.0, 2.0, 4.0)


class FetchError(RuntimeError):
    """Network/replay failure for one logical fetch (grid or points)."""


@dataclass(frozen=True)
class RawResponse:
    cache_key: str
    endpoint: str
    params: Mapping[str, str]
    fetched_at: str
    hour_bucket: str
    response: Any
    cache_hit: bool
    path: Path | None


class OpenMeteoClient:
    """Live client with disk cache, or a replay transport over stored files."""

    def __init__(
        self,
        cache_dir: Path,
        hour_bucket: str,
        use_cache: bool = True,
        replay_dir: Path | None = None,
        sleep=time.sleep,
    ) -> None:
        self.cache_dir = cache_dir
        self.hour_bucket = hour_bucket
        self.use_cache = use_cache
        self.replay_dir = replay_dir
        self.sleep = sleep
        self.session = requests.Session()

    def fetch(self, kind: str, params: Mapping[str, str]) -> RawResponse:
        key = cache_key(FORECAST_URL, params, self.hour_bucket)
        if self.replay_dir is not None:
            return self._from_file(self.replay_dir / f"{key}.json", key, hit=True)
        if os.environ.get("EWS_FAKE_NET_FAIL") == kind:
            raise FetchError(f"simulated network failure for kind={kind}")
        cache_path = self.cache_dir / f"{key}.json"
        if self.use_cache and cache_path.is_file():
            return self._from_file(cache_path, key, hit=True)
        body = self._http_get(params)
        fetched_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        record = {
            "endpoint": FORECAST_URL,
            "params": dict(params),
            "fetched_at": fetched_at,
            "hour_bucket": self.hour_bucket,
            "response": body,
        }
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        tmp = cache_path.with_suffix(".tmp")
        tmp.write_text(json.dumps(record, sort_keys=True), encoding="utf-8")
        tmp.replace(cache_path)
        return RawResponse(key, FORECAST_URL, dict(params), fetched_at,
                           self.hour_bucket, body, False, cache_path)

    def _from_file(self, path: Path, key: str, hit: bool) -> RawResponse:
        if not path.is_file():
            raise FetchError(f"replay/cache miss for {path.name}")
        record = json.loads(path.read_text(encoding="utf-8"))
        return RawResponse(key, record["endpoint"], record["params"],
                           record["fetched_at"], record["hour_bucket"],
                           record["response"], hit, path)

    def _http_get(self, params: Mapping[str, str]) -> Any:
        last_error: Exception | None = None
        for attempt, backoff in enumerate((*RETRY_BACKOFF_S, None)):
            try:
                reply = self.session.get(FORECAST_URL, params=dict(params), timeout=30)
                if reply.status_code == 429 or reply.status_code >= 500:
                    raise FetchError(f"HTTP {reply.status_code}: {reply.text[:200]}")
                reply.raise_for_status()
                return reply.json()
            except (FetchError, requests.RequestException) as exc:
                last_error = exc
                if backoff is None:
                    break
                self.sleep(backoff)
        raise FetchError(f"open-meteo request failed after retries: {last_error}")


def cache_key(endpoint: str, params: Mapping[str, str], hour_bucket: str) -> str:
    canonical = json.dumps(
        {"endpoint": endpoint, "hour": hour_bucket, "params": dict(sorted(params.items()))},
        sort_keys=True,
    )
    return sha256(canonical.encode("utf-8")).hexdigest()


def utc_hour_bucket(moment: datetime) -> str:
    return moment.astimezone(timezone.utc).strftime("%Y-%m-%dT%H")


# ---------------------------------------------------------------- point fetch

def fetch_point_forecasts(client: OpenMeteoClient, communes) -> RawResponse:
    """ONE batched call for all communes (7-day hourly + daily + 2 past days)."""
    params = {
        "latitude": ",".join(f"{c.lat:.4f}" for c in communes),
        "longitude": ",".join(f"{c.lon:.4f}" for c in communes),
        "elevation": ",".join(f"{c.elevation_m:.0f}" for c in communes),
        "hourly": POINT_HOURLY,
        "daily": POINT_DAILY,
        "forecast_days": "7",
        "past_days": "2",
        "timezone": "UTC",
        "wind_speed_unit": "ms",
        "models": "best_match",
    }
    return client.fetch("points", params)


def point_blocks(raw: RawResponse, communes) -> dict[str, dict[str, Any]]:
    """Per-commune-code {hourly, daily, elevation} from the batched response."""
    body = raw.response if isinstance(raw.response, list) else [raw.response]
    if len(body) != len(communes):
        raise FetchError(f"expected {len(communes)} locations, got {len(body)}")
    return {
        commune.code: {
            "hourly": location["hourly"],
            "daily": location["daily"],
            "elevation": location.get("elevation"),
        }
        for commune, location in zip(communes, body)
    }


# ----------------------------------------------------------------- grid fetch

def stride2_latlons() -> tuple[list[float], list[float], tuple[int, int]]:
    """Row-major stride-2 subgrid centers; row 0 = northernmost."""
    sub_rows = range(0, GRID_SHAPE[0], 2)
    sub_cols = range(0, GRID_SHAPE[1], 2)
    lats, lons = [], []
    for row in sub_rows:
        for col in sub_cols:
            lats.append(round(LAT0 - row * DLAT, 4))
            lons.append(round(LON0 + col * DLON, 4))
    return lats, lons, (len(sub_rows), len(sub_cols))


def fetch_grid_chunks(client: OpenMeteoClient) -> list[RawResponse]:
    lats, lons, _ = stride2_latlons()
    chunks: list[RawResponse] = []
    for start in range(0, len(lats), GRID_CHUNK_SIZE):
        if start and client.replay_dir is None:
            client.sleep(GRID_CALL_SPACING_S)
        params = {
            "latitude": ",".join(str(v) for v in lats[start : start + GRID_CHUNK_SIZE]),
            "longitude": ",".join(str(v) for v in lons[start : start + GRID_CHUNK_SIZE]),
            "hourly": GRID_HOURLY,
            "forecast_days": "1",
            "past_days": "1",
            "timezone": "UTC",
            "wind_speed_unit": "ms",
        }
        chunks.append(client.fetch("grid", params))
    return chunks


# ------------------------------------------------- physics helper derivations

def wind_uv(speed: np.ndarray, direction_deg: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Meteorological convention: direction is where wind comes FROM."""
    radians = np.deg2rad(direction_deg)
    return -speed * np.sin(radians), -speed * np.cos(radians)


def magnus_dewpoint_c(temp_c: np.ndarray, rh_pct: np.ndarray) -> np.ndarray:
    gamma = np.log(rh_pct / 100.0) + 17.62 * temp_c / (243.12 + temp_c)
    return 243.12 * gamma / (17.62 - gamma)


def k_index(t850, t700, t500, rh850, rh700) -> np.ndarray:
    td850 = magnus_dewpoint_c(t850, rh850)
    td700 = magnus_dewpoint_c(t700, rh700)
    return (t850 - t500) + td850 - (t700 - td700)


# ------------------------------------------------------------- grid assembly

@dataclass(frozen=True)
class GridBuild:
    grids: dict[str, np.ndarray] | None
    substitutions: tuple[dict[str, Any], ...]
    grid_mode: str
    stats: dict[str, Any]


def build_grids(
    chunks: Iterable[RawResponse],
    tick_time: datetime,
    training_means: Mapping[str, float],
) -> GridBuild:
    """10 nowcast feature grids for tick_time from the stride-2 chunk responses."""
    locations = [loc for chunk in chunks
                 for loc in (chunk.response if isinstance(chunk.response, list)
                             else [chunk.response])]
    _, _, sub_shape = stride2_latlons()
    if len(locations) != sub_shape[0] * sub_shape[1]:
        raise FetchError(f"grid fetch returned {len(locations)} points, "
                         f"expected {sub_shape[0] * sub_shape[1]}")
    hour_key = tick_time.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:00")
    raw = _subgrids_at_hour(locations, hour_key, sub_shape)
    if raw is None:
        return GridBuild(None, (), "stride2_nn",
                         {"error": f"hour {hour_key} not in grid response"})
    u850, v850 = wind_uv(raw["wind_speed_850hPa"], raw["wind_direction_850hPa"])
    u250, v250 = wind_uv(raw["wind_speed_250hPa"], raw["wind_direction_250hPa"])
    features = {
        "AWS2": raw["precipitation"],
        "CAPE": raw["cape"],
        "CIN": raw["convective_inhibition"],
        "U850": u850, "V850": v850, "U250": u250, "V250": v250,
        "R250": raw["relative_humidity_250hPa"],
        "KX": k_index(raw["temperature_850hPa"], raw["temperature_700hPa"],
                      raw["temperature_500hPa"], raw["relative_humidity_850hPa"],
                      raw["relative_humidity_700hPa"]),
        "EWSS": np.full(sub_shape, np.nan),  # no live source -> substitution
    }
    return _upsample_and_substitute(features, training_means)


def _subgrids_at_hour(locations, hour_key: str, sub_shape) -> dict[str, np.ndarray] | None:
    """Per-raw-variable (20, 19) arrays at one UTC hour; None if hour unavailable."""
    try:
        indices = [loc["hourly"]["time"].index(hour_key) for loc in locations]
    except ValueError:
        return None
    variables = [name for name in GRID_HOURLY.split(",") if name != "lifted_index"]
    subgrids: dict[str, np.ndarray] = {}
    for name in variables:
        values = [loc["hourly"].get(name, [None] * len(loc["hourly"]["time"]))[idx]
                  for loc, idx in zip(locations, indices)]
        column = [math.nan if v is None else float(v) for v in values]
        subgrids[name] = np.asarray(column, dtype=np.float64).reshape(sub_shape)
    return subgrids


def _upsample_and_substitute(
    features: dict[str, np.ndarray], training_means: Mapping[str, float]
) -> GridBuild:
    """Nearest-neighbor stride-2 upsample + training-mean substitution of nulls."""
    grids: dict[str, np.ndarray] = {}
    substitutions: list[dict[str, Any]] = []
    stats: dict[str, Any] = {}
    for name, subgrid in features.items():
        full = np.repeat(np.repeat(subgrid, 2, axis=0), 2, axis=1)
        full = full[: GRID_SHAPE[0], : GRID_SHAPE[1]]
        missing = np.isnan(full)
        if missing.any():
            # Training mean standardizes to z=0 ("nothing unusual") — never 0.
            full = np.where(missing, training_means[name], full)
            substitutions.append({
                "var": name, "mode": "training_mean",
                "fraction": round(float(missing.mean()), 4),
            })
        grids[name] = full.astype(np.float32)
        stats[name] = {"min": round(float(full.min()), 3),
                       "mean": round(float(full.mean()), 3),
                       "max": round(float(full.max()), 3)}
    return GridBuild(grids, tuple(substitutions), "stride2_nn", stats)


# ------------------------------------------------------------------- scaler

def load_scaler_meta(scaler_path: Path) -> tuple[dict[str, float], str]:
    """Per-feature training means + scaler status ('dummy' or 'fitted')."""
    payload = json.loads(scaler_path.read_text(encoding="utf-8"))
    means = dict(zip(payload["feature_order"], payload["mean"]))
    status = "dummy" if "DUMMY" in str(payload.get("fitted_on", "")).upper() else "fitted"
    return means, status
