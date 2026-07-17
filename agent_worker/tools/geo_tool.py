"""Tool địa lý — wrap app.services.geo_data (danh mục xã Điện Biên + toạ độ)."""

from __future__ import annotations

from agent_worker.shared import geo_data


def get_commune(code: str) -> dict | None:
    c = geo_data.get_commune(code)
    return c.model_dump() if c else None


def all_communes() -> list[dict]:
    return [c.model_dump() for c in geo_data.all_communes()]
