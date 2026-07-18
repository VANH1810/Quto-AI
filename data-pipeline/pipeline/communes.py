"""Nạp danh mục 45 xã (centroid + độ cao) từ data/communes.json."""

from __future__ import annotations

import json

from pipeline.config import DATA_DIR


def load_communes() -> list[dict]:
    """Mỗi phần tử: {code, name, lat, lon, elevation_m}."""
    path = DATA_DIR / "communes.json"
    with open(path, encoding="utf-8") as f:
        return json.load(f)
