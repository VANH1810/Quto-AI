"""Nguồn dữ liệu THẬT từ Supabase (PostgREST) cho agent — dùng khi DATA_SOURCE=supabase.

Chỉ lo dữ liệu nghiệp vụ ĐỌC (citizens/admins/shelters) + ghi onboarding Telegram vào citizens
+ mirror notifications. Trace (agent_runs/agent_spans/home_visits) vẫn ở Postgres local (repo.py).

Dùng supabase-py **AsyncClient** (`create_async_client`) → mọi lệnh `await` native, KHÔNG block
event loop (không cần to_thread). Client tạo 1 lần / process, khởi tạo lười trong coroutine.
Hình dạng dict trả về giữ giống `data_repo._row()` để message_formatter/tasks không phải đổi.
"""

from __future__ import annotations

import logging
import secrets

from supabase import AsyncClient, create_async_client

from agent_worker.config import get_worker_settings
from agent_worker.shared.geo_data import haversine_km

log = logging.getLogger("agent_worker.supabase")

_client: AsyncClient | None = None


async def _c() -> AsyncClient:
    global _client
    if _client is None:
        s = get_worker_settings()
        if not s.supabase_url or not s.supabase_key:
            raise RuntimeError("DATA_SOURCE=supabase nhưng thiếu SUPABASE_URL / SUPABASE_KEY.")
        _client = await create_async_client(s.supabase_url, s.supabase_key)
    return _client


# ------------------------------------------------------------------ ĐỌC dữ liệu

async def citizens_by_commune(code: str) -> list[dict]:
    c = await _c()
    r = await c.table("citizens").select("*").eq("commune_code", code).execute()
    return r.data or []


async def admins_for_commune(code: str) -> list[dict]:
    c = await _c()
    r = await c.table("admins").select("*").execute()          # communes là mảng → lọc Python
    return [a for a in (r.data or []) if code in (a.get("communes") or [])]


async def _shelters(code: str) -> list[dict]:
    c = await _c()
    r = await c.table("shelters").select("*").eq("commune_code", code).execute()
    return r.data or []


async def nearest_shelter(code: str, lat: float | None, lon: float | None) -> dict | None:
    rows = await _shelters(code)
    if not rows:
        return None
    if lat is None or lon is None:
        return rows[0]
    best = min(rows, key=lambda sh: haversine_km(lat, lon, sh["lat"], sh["lon"]))
    d = dict(best)
    d["distance_km"] = haversine_km(lat, lon, best["lat"], best["lon"])
    return d


async def nearest_for_commune(code: str, citizens: list[dict]) -> dict[str, dict]:
    """Nạp shelters của xã 1 LẦN, haversine gần nhất trong Python cho từng công dân."""
    shelters = await _shelters(code)
    if not shelters:
        return {}
    out: dict[str, dict] = {}
    for c in citizens:
        lat, lon = c.get("lat"), c.get("lon")
        if lat is None or lon is None:
            continue
        best = min(shelters, key=lambda sh: haversine_km(lat, lon, sh["lat"], sh["lon"]))
        d = dict(best)
        d["distance_km"] = haversine_km(lat, lon, best["lat"], best["lon"])
        out[c["cccd"]] = d
    return out


# --------------------------------------------------- Telegram onboarding (GHI citizens)

async def ensure_link_tokens(code: str) -> list[dict]:
    """Sinh telegram_link_token (nếu chưa có) cho từng công dân của xã, lưu lên Supabase."""
    c = await _c()
    r = await c.table("citizens").select("cccd,full_name,telegram_link_token") \
        .eq("commune_code", code).execute()
    out = []
    for row in r.data or []:
        tok = row.get("telegram_link_token")
        if not tok:
            tok = secrets.token_urlsafe(12)
            await c.table("citizens").update({"telegram_link_token": tok}) \
                .eq("cccd", row["cccd"]).execute()
        out.append({"cccd": row["cccd"], "full_name": row["full_name"],
                    "telegram_link_token": tok})
    return out


async def set_telegram_chat_id_by_token(token: str, chat_id: str) -> dict | None:
    c = await _c()
    r = await c.table("citizens").update({"telegram_chat_id": str(chat_id)}) \
        .eq("telegram_link_token", token).execute()
    row = (r.data or [None])[0]
    if not row:
        return None
    return {"cccd": row.get("cccd"), "full_name": row.get("full_name"),
            "telegram_chat_id": row.get("telegram_chat_id")}


# --------------------------------------------------- GHI notifications (mirror)

async def add_notification(payload: dict) -> None:
    c = await _c()
    await c.table("notifications").insert(payload).execute()
