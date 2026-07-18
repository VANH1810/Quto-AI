"""Tool tìm nơi trú ẩn — đọc THẲNG Postgres (data_repo), haversine gần nhất.

Giữ tên hàm cũ để nodes không phải sửa.
"""

from __future__ import annotations

from agent_worker import data_repo


async def nearest(code: str, lat: float | None, lon: float | None) -> dict | None:
    return await data_repo.nearest_shelter(code, lat, lon)


async def nearest_for_commune(code: str, citizens: list[dict]) -> dict[str, dict]:
    return await data_repo.nearest_for_commune(code, citizens)
