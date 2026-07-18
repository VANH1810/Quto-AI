"""Redis phụ trợ cho worker — cache OA access token của Zalo.

Trạng thái/kết quả job KHÔNG lưu ở đây nữa: Celery result backend (Redis) giữ
state + metadata, polling qua AsyncResult (xem tasks.py / infra_client.py).
"""

from __future__ import annotations

import redis.asyncio as aioredis

from agent_worker.config import get_worker_settings

_client: aioredis.Redis | None = None


async def client() -> aioredis.Redis:
    global _client
    if _client is None:
        _client = aioredis.from_url(get_worker_settings().redis_url,
                                    encoding="utf-8", decode_responses=True)
    return _client


async def cache_zalo_token(token: str, ttl: int) -> None:
    c = await client()
    await c.set("agent:zalo:token", token, ex=max(60, ttl - 60))


async def get_zalo_token() -> str | None:
    c = await client()
    return await c.get("agent:zalo:token")
