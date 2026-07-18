"""Tool truy vấn/ghi dữ liệu người dùng — đọc/ghi THẲNG Postgres của backend AI.

Trước đây gọi REST sang backend cũ; nay agent_worker tự chứa dữ liệu nên dùng
data_repo (cùng DB). Giữ nguyên tên hàm để nodes/tasks không phải sửa.
"""

from __future__ import annotations

from agent_worker import data_repo


async def citizens_by_commune(code: str) -> list[dict]:
    return await data_repo.citizens_by_commune(code)


async def admins_for_commune(code: str) -> list[dict]:
    return await data_repo.admins_for_commune(code)


async def create_notification(payload: dict) -> dict:
    return await data_repo.add_notification(payload)


async def create_home_visit(payload: dict) -> dict:
    return await data_repo.add_home_visit(payload)
