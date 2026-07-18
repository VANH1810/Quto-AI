"""Lớp truy cập Supabase (Postgres qua PostgREST) — tuỳ chọn.

Bật bằng `.env`: DB_BACKEND=supabase + SUPABASE_URL + SUPABASE_KEY (service_role).
Khi TẮT (mặc định memory): app chạy hoàn toàn in-memory, không cần Supabase.

Chức năng:
  - push_* : đẩy dữ liệu (communes/citizens/shelters/notifications) LÊN Supabase (upsert).
  - fetch_*: kéo citizens/shelters TỪ Supabase về (để nạp vào store khi khởi động).

supabase-py là SYNC; gọi trong route async vẫn ổn cho quy mô demo.
"""

from __future__ import annotations

import concurrent.futures
from functools import lru_cache
from typing import Any

from app.config import get_settings

# Thread pool để đẩy dữ liệu lên Supabase ở chế độ nền (không chặn request).
_EXECUTOR = concurrent.futures.ThreadPoolExecutor(max_workers=4, thread_name_prefix="supa-mirror")


@lru_cache
def _client():
    settings = get_settings()
    if not settings.supabase_url or not settings.supabase_key:
        return None
    from supabase import create_client  # import trễ để không bắt buộc cài khi dùng memory
    return create_client(settings.supabase_url, settings.supabase_key)


def enabled() -> bool:
    s = get_settings()
    return s.db_backend.lower() == "supabase" and bool(s.supabase_url and s.supabase_key)


def _upsert(table: str, models: list[Any], on_conflict: str,
            exclude: set[str] | None = None) -> int:
    client = _client()
    if client is None or not models:
        return 0
    rows = [m.model_dump(mode="json", exclude=exclude) for m in models]
    client.table(table).upsert(rows, on_conflict=on_conflict).execute()
    return len(models)


# ---- PUSH (đẩy lên) ----
def push_communes(communes: list[Any]) -> int:
    return _upsert("communes", communes, on_conflict="code")


def push_citizens(citizens: list[Any]) -> int:
    return _upsert("citizens", citizens, on_conflict="cccd")


def push_shelters(shelters: list[Any]) -> int:
    # distance_km là giá trị tính lúc truy vấn, KHÔNG phải cột trong DB.
    return _upsert("shelters", shelters, on_conflict="id", exclude={"distance_km"})


def push_notifications(notifs: list[Any]) -> int:
    return _upsert("notifications", notifs, on_conflict="id")


def push_rescue_requests(reqs: list[Any]) -> int:
    return _upsert("rescue_requests", reqs, on_conflict="id")


def push_rescue_teams(teams: list[Any]) -> int:
    return _upsert("rescue_teams", teams, on_conflict="id")


def push_loudspeakers(speakers: list[Any]) -> int:
    return _upsert("loudspeakers", speakers, on_conflict="id")


def push_interactions(logs: list[Any]) -> int:
    return _upsert("interaction_logs", logs, on_conflict="id")


def push_admins(records: list[Any]) -> int:
    """Admin là dataclass (không phải pydantic) → tự dựng row."""
    client = _client()
    if client is None or not records:
        return 0
    rows = [{
        "id": r.id, "email": r.email, "full_name": r.full_name, "age": r.age,
        "phone": r.phone, "ethnicity": r.ethnicity, "religion": r.religion,
        "role": r.role.value if hasattr(r.role, "value") else r.role,
        "communes": r.communes, "password_hash": r.password_hash,
    } for r in records]
    client.table("admins").upsert(rows, on_conflict="id").execute()
    return len(records)


def _safe_push(push_fn, items) -> None:
    try:
        push_fn(items)
    except Exception:  # noqa: BLE001 — mất mạng/thiếu bảng không được làm hỏng luồng chính
        pass


def mirror(push_fn, items) -> None:
    """Đẩy lên Supabase CHẠY NỀN (fire-and-forget) — request trả về ngay, không chờ mạng.

    Nhờ vậy API SOS/cảnh báo/tin nhắn phản hồi nhanh; dữ liệu lên Supabase ngay sau đó,
    FE (subscribe Supabase Realtime) nhận cập nhật gần như tức thì.
    """
    if not enabled() or not items:
        return
    _EXECUTOR.submit(_safe_push, push_fn, list(items))


# ---- FETCH (kéo về) ----
def fetch_admins() -> list[dict]:
    client = _client()
    if client is None:
        return []
    return client.table("admins").select("*").execute().data or []


def fetch_citizens() -> list[dict]:
    client = _client()
    if client is None:
        return []
    return client.table("citizens").select("*").execute().data or []


def fetch_rescue_requests() -> list[dict]:
    client = _client()
    if client is None:
        return []
    return client.table("rescue_requests").select("*").execute().data or []


def fetch_shelters() -> list[dict]:
    client = _client()
    if client is None:
        return []
    return client.table("shelters").select("*").execute().data or []
