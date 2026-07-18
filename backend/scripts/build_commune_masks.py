from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
from rasterio.features import rasterize
from rasterio.transform import from_origin

from nowcast.grid_constants import DLAT, DLON, GRID_SHAPE, LAT0, LON0


def build_masks(geojson_path: Path, output_path: Path) -> None:
    import json

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
    output_path.parent.mkdir(parents=True, exist_ok=True)
    metadata = np.array([LAT0, LON0, DLAT, DLON, *GRID_SHAPE])
    np.savez_compressed(
        output_path, grid_metadata=metadata, commune_codes=codes, **arrays
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Rasterize commune polygons onto the model grid"
    )
    parser.add_argument("geojson_path", type=Path)
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("backend/nowcast/artifacts/commune_masks.npz"),
    )
    args = parser.parse_args()
    build_masks(args.geojson_path, args.output)


if __name__ == "__main__":
    main()
