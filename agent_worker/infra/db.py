"""Postgres (SQLAlchemy 2.0 async) — DB TỰ CHỨA của backend AI.

(A) dữ liệu: citizens/admins/shelters/notifications/home_visits.
(B) vết LLM: agent_runs + agent_spans.
init_models() chạy db/schema.sql (idempotent) lúc boot.
"""

from __future__ import annotations

import logging
import threading
from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncIterator

from sqlalchemy import (Boolean, Float, Integer, String, Text, text)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, TIMESTAMP
from sqlalchemy.ext.asyncio import (AsyncSession, async_sessionmaker,
                                    create_async_engine)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy.sql import func

from agent_worker.config import get_worker_settings

log = logging.getLogger("agent_worker.db")

_SCHEMA_FILE = Path(__file__).resolve().parent.parent / "db" / "schema.sql"

# Engine + sessionmaker RIÊNG mỗi thread: Celery threads pool cho mỗi thread 1 event
# loop; AsyncEngine phải gắn đúng 1 loop → tạo theo-thread. Nhờ vậy DÙNG pool thật
# (tái dùng connection) thay cho NullPool → hết churn connect/disconnect mỗi thao tác.
_local = threading.local()


def _sessionmaker() -> async_sessionmaker[AsyncSession]:
    sm = getattr(_local, "sm", None)
    if sm is None:
        eng = create_async_engine(
            get_worker_settings().database_url,
            pool_size=5, max_overflow=5, pool_pre_ping=True,
        )
        _local.engine = eng
        sm = async_sessionmaker(eng, expire_on_commit=False)
        _local.sm = sm
    return sm


class Base(DeclarativeBase):
    pass


# ---------------------------------------------------------------- (A) dữ liệu

class Citizen(Base):
    __tablename__ = "citizens"
    cccd: Mapped[str] = mapped_column(String, primary_key=True)
    full_name: Mapped[str] = mapped_column(String)
    age: Mapped[int | None] = mapped_column(Integer, nullable=True)
    address: Mapped[str | None] = mapped_column(String, nullable=True)
    phone: Mapped[str | None] = mapped_column(String, nullable=True)
    ethnicity: Mapped[str | None] = mapped_column(String, nullable=True)
    commune_code: Mapped[str | None] = mapped_column(String, index=True, nullable=True)
    lat: Mapped[float | None] = mapped_column(Float, nullable=True)
    lon: Mapped[float | None] = mapped_column(Float, nullable=True)
    consent_zalo_sms: Mapped[bool] = mapped_column(Boolean, default=True)
    preferred_lang: Mapped[str] = mapped_column(String, default="vi")
    telegram_chat_id: Mapped[str | None] = mapped_column(String, nullable=True)
    telegram_link_token: Mapped[str | None] = mapped_column(String, nullable=True)


class Admin(Base):
    __tablename__ = "admins"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    full_name: Mapped[str] = mapped_column(String)
    email: Mapped[str | None] = mapped_column(String, nullable=True)
    phone: Mapped[str | None] = mapped_column(String, nullable=True)
    communes: Mapped[list[str] | None] = mapped_column(ARRAY(String), nullable=True)


class Shelter(Base):
    __tablename__ = "shelters"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    commune_code: Mapped[str | None] = mapped_column(String, index=True, nullable=True)
    name: Mapped[str] = mapped_column(String)
    address: Mapped[str | None] = mapped_column(String, nullable=True)
    lat: Mapped[float | None] = mapped_column(Float, nullable=True)
    lon: Mapped[float | None] = mapped_column(Float, nullable=True)
    capacity: Mapped[int] = mapped_column(Integer, default=0)
    kind: Mapped[str] = mapped_column(String, default="community_hall")
    contact_phone: Mapped[str | None] = mapped_column(String, nullable=True)


class Notification(Base):
    __tablename__ = "notifications"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    alert_id: Mapped[str | None] = mapped_column(String, index=True, nullable=True)
    cccd: Mapped[str | None] = mapped_column(String, index=True, nullable=True)
    full_name: Mapped[str | None] = mapped_column(String, nullable=True)
    address: Mapped[str | None] = mapped_column(String, nullable=True)
    commune_code: Mapped[str | None] = mapped_column(String, nullable=True)
    channel: Mapped[str | None] = mapped_column(String, nullable=True)
    lang: Mapped[str | None] = mapped_column(String, nullable=True)
    status: Mapped[str | None] = mapped_column(String, nullable=True)
    nearest_shelter_id: Mapped[str | None] = mapped_column(String, nullable=True)
    nearest_shelter_name: Mapped[str | None] = mapped_column(String, nullable=True)
    nearest_shelter_address: Mapped[str | None] = mapped_column(String, nullable=True)
    nearest_shelter_km: Mapped[float | None] = mapped_column(Float, nullable=True)
    detail: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[object] = mapped_column(TIMESTAMP(timezone=True), server_default=func.now())


class HomeVisit(Base):
    __tablename__ = "home_visits"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    alert_id: Mapped[str | None] = mapped_column(String, nullable=True)
    commune_code: Mapped[str | None] = mapped_column(String, nullable=True)
    assigned_admin_id: Mapped[str | None] = mapped_column(String, nullable=True)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String, default="open")
    created_at: Mapped[object] = mapped_column(TIMESTAMP(timezone=True), server_default=func.now())


# ---------------------------------------------------------------- (B) vết LLM

class AgentRun(Base):
    __tablename__ = "agent_runs"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    alert_id: Mapped[str | None] = mapped_column(String, nullable=True)
    commune_code: Mapped[str | None] = mapped_column(String, nullable=True)
    trigger: Mapped[str | None] = mapped_column(String, nullable=True)
    status: Mapped[str] = mapped_column(String, default="running")
    risk_level: Mapped[int | None] = mapped_column(Integer, nullable=True)
    langs: Mapped[list[str] | None] = mapped_column(ARRAY(String), nullable=True)
    llm_provider: Mapped[str | None] = mapped_column(String, nullable=True)
    llm_model: Mapped[str | None] = mapped_column(String, nullable=True)
    prompt_tokens: Mapped[int] = mapped_column(Integer, default=0)
    completion_tokens: Mapped[int] = mapped_column(Integer, default=0)
    total_tokens: Mapped[int] = mapped_column(Integer, default=0)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[object] = mapped_column(TIMESTAMP(timezone=True), server_default=func.now())
    updated_at: Mapped[object] = mapped_column(TIMESTAMP(timezone=True), server_default=func.now())
    finished_at: Mapped[object | None] = mapped_column(TIMESTAMP(timezone=True), nullable=True)


class AgentSpan(Base):
    __tablename__ = "agent_spans"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    run_id: Mapped[str] = mapped_column(String, index=True)
    parent_span_id: Mapped[str | None] = mapped_column(String, nullable=True)
    seq: Mapped[int] = mapped_column(Integer)
    kind: Mapped[str] = mapped_column(String)                 # node | tool | llm
    name: Mapped[str] = mapped_column(String)
    status: Mapped[str] = mapped_column(String, default="running")
    input: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    output: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    content: Mapped[str | None] = mapped_column(Text, nullable=True)
    thinking: Mapped[str | None] = mapped_column(Text, nullable=True)
    prompt_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    completion_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    total_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    finish_reason: Mapped[str | None] = mapped_column(String, nullable=True)
    latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[object] = mapped_column(TIMESTAMP(timezone=True), server_default=func.now())


async def init_models() -> None:
    """Chạy schema_llm.sql (idempotent). Bỏ qua nếu Postgres chưa sẵn sàng sẽ raise."""
    sql = _SCHEMA_FILE.read_text(encoding="utf-8")
    # Bỏ các dòng comment (-- ...) trước khi tách theo ';' để header không dính vào
    # statement đầu và bị loại nhầm.
    code = "\n".join(ln for ln in sql.splitlines() if not ln.strip().startswith("--"))
    statements = [s.strip() for s in code.split(";") if s.strip()]
    _sessionmaker()   # đảm bảo engine của thread đã tạo
    async with _local.engine.begin() as conn:
        for stmt in statements:
            await conn.execute(text(stmt))
    log.info("Đã khởi tạo DB backend AI (data + agent_runs/agent_spans).")


@asynccontextmanager
async def session() -> AsyncIterator[AsyncSession]:
    async with _sessionmaker()() as s:
        try:
            yield s
            await s.commit()
        except Exception:
            await s.rollback()
            raise
