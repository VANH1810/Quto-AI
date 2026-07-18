"""Tool dữ liệu người dùng.

- Recipients (citizens/admins): đọc THẲNG Postgres của agent_worker (data_repo).
- Ghi tin nhắn cá nhân (notifications): CALLBACK REST về backend (BACKEND_URL) kèm
  X-Service-Token. Dùng lại 1 httpx client theo-thread (keep-alive) → tránh bắt tay
  TCP mỗi lần callback khi fan-out hàng trăm người nhận.
"""

from __future__ import annotations

import threading

import httpx

from agent_worker import data_repo
from agent_worker.config import get_worker_settings

_clients = threading.local()   # AsyncClient gắn theo event loop của từng thread


def _client() -> httpx.AsyncClient:
    c = getattr(_clients, "c", None)
    if c is None or c.is_closed:
        c = httpx.AsyncClient(timeout=12,
                              limits=httpx.Limits(max_keepalive_connections=10, max_connections=20))
        _clients.c = c
    return c


async def citizens_by_commune(code: str) -> list[dict]:
    return await data_repo.citizens_by_commune(code)


async def admins_for_commune(code: str) -> list[dict]:
    return await data_repo.admins_for_commune(code)


async def create_notification(payload: dict) -> dict:
    """POST tin nhắn cá nhân về backend (callback), tái dùng client theo-thread."""
    s = get_worker_settings()
    r = await _client().post(f"{s.backend_url}/api/v1/agent/notifications", json=payload,
                             headers={"X-Service-Token": s.service_token})
    r.raise_for_status()
    return r.json()
