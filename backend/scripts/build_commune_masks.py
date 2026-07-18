from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

import numpy as np

from nowcast.grid_constants import DLAT, DLON, GRID_SHAPE, LAT0, LON0

DEFAULT_OUTPUT = Path("backend/nowcast/artifacts/commune_masks.npz")
KM_PER_DEG = 111.32


def build_masks(geojson_path: Path, output_path: Path) -> None:
    # rasterio is only needed for real polygons; the provisional-circles path
    # below must work in environments without GDAL.
    from rasterio.features import rasterize
    from rasterio.transform import from_origin

    data = json.loads(geojson_path.read_text(encoding="utf-8"))
    transform = from_origin(LON0 - DLON / 2, LAT0 + DLAT / 2, DLON, DLAT)
    arrays: dict[str, np.ndarray] = {}
    codes = []
    for feature in data["features"]:
        properties = feature["properties"]
        code = str(properties.get("commune_code", properties.get("code", "")))
        if not code:
            raise ValueError("every GeoJSON feature needs commune_code or code")
        codes.append(code)
        arrays[f"mask_{code}"] = rasterize(
            [(feature["geometry"], 1)], out_shape=GRID_SHAPE, transform=transform
        ).astype(bool)
    _save(output_path, codes, arrays, masks_version="geojson_v1")


def build_provisional_circle_masks(output_path: Path, radius_km: float) -> None:
    """No official polygons yet: ~radius_km circles around registry centroids."""
    from pipeline.communes import COMMUNES

    rows = LAT0 - DLAT * np.arange(GRID_SHAPE[0])  # row 0 = northernmost
    cols = LON0 + DLON * np.arange(GRID_SHAPE[1])
    lat_grid, lon_grid = np.meshgrid(rows, cols, indexing="ij")
    arrays: dict[str, np.ndarray] = {}
    codes = []
    for commune in COMMUNES:
        dy_km = (lat_grid - commune.lat) * KM_PER_DEG
        dx_km = (lon_grid - commune.lon) * KM_PER_DEG * math.cos(math.radians(commune.lat))
        mask = np.hypot(dx_km, dy_km) <= radius_km
        if not mask.any():
            raise ValueError(f"empty provisional mask for {commune.code}")
        codes.append(commune.code)
        arrays[f"mask_{commune.code}"] = mask
    _save(output_path, codes, arrays, masks_version="provisional_circles_v1")


def _save(
    output_path: Path,
    codes: list[str],
    arrays: dict[str, np.ndarray],
    masks_version: str,
) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    metadata = np.array([LAT0, LON0, DLAT, DLON, *GRID_SHAPE])
    np.savez_compressed(
        output_path,
        grid_metadata=metadata,
        commune_codes=codes,
        masks_version=np.array(masks_version),
        **arrays,
    )
    sizes = {code: int(arrays[f"mask_{code}"].sum()) for code in codes}
    print(f"wrote {output_path} version={masks_version} pixels={sizes}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Rasterize commune polygons (or provisional circles) onto the model grid"
    )
    parser.add_argument("geojson_path", type=Path, nargs="?")
    parser.add_argument("--provisional-circles", action="store_true")
    parser.add_argument("--radius-km", type=float, default=6.0)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    if args.provisional_circles:
        build_provisional_circle_masks(args.output, args.radius_km)
    elif args.geojson_path is not None:
        build_masks(args.geojson_path, args.output)
    else:
        parser.error("pass a GeoJSON path or --provisional-circles")


if __name__ == "__main__":
    main()
