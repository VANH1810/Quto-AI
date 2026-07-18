"""Tầng dữ liệu nghiệp vụ của backend AI (Postgres) — worker & agent-api dùng chung.

citizens / admins / shelters / notifications / home_visits. Thay cho việc gọi REST
sang backend cũ: worker đọc/ghi THẲNG DB này.
"""

from __future__ import annotations

import secrets
import uuid

from sqlalchemy import delete, select

from agent_worker.infra.db import (Admin, Citizen, HomeVisit, Notification,
                                   Shelter, session)
from agent_worker.shared.geo_data import haversine_km

_LANG_BY_ETH = {"thái": "tai", "thai": "tai", "mông": "hmn", "mong": "hmn",
                "hmong": "hmn", "h'mông": "hmn"}


def _lang(ethnicity: str | None) -> str:
    return _LANG_BY_ETH.get((ethnicity or "").strip().lower(), "vi")


def _row(obj) -> dict:
    return {c.name: getattr(obj, c.name) for c in obj.__table__.columns}


# --------------------------------------------------------------------- seed

_SEED_ADMINS = [
    dict(id="adm_canbo", full_name="Lò Văn Panh", email="canbo@dienbien.gov.vn",
         phone="0961000001", communes=["muong_pon", "tua_chua"]),
]
_SEED_CITIZENS = [
    dict(cccd="040094000001", full_name="Lò Thị Ánh", age=34, address="Bản Nậm Pồn, Xã Mường Pồn",
         phone="0971000001", ethnicity="Thái", commune_code="muong_pon", lat=21.531, lon=103.081,
         consent_zalo_sms=True),
    dict(cccd="040094000002", full_name="Vàng A Sùng", age=41, address="Bản Huổi Chan, Xã Mường Pồn",
         phone="0971000002", ethnicity="Mông", commune_code="muong_pon", lat=21.528, lon=103.079,
         consent_zalo_sms=True),
    dict(cccd="040094000003", full_name="Nguyễn Văn Bình", age=52, address="Trung tâm xã, Xã Mường Pồn",
         phone="0971000003", ethnicity="Kinh", commune_code="muong_pon", lat=21.530, lon=103.080,
         consent_zalo_sms=False),   # không đồng ý → chỉ nhận qua loa
    dict(cccd="040094000004", full_name="Giàng Thị Mai", age=29, address="TT Tủa Chùa",
         phone="0971000004", ethnicity="Mông", commune_code="tua_chua", lat=21.991, lon=103.360,
         consent_zalo_sms=True),
]
_SEED_SHELTERS = [
    dict(id="shl_mp1", commune_code="muong_pon", name="Trường PTDTBT Tiểu học Mường Pồn",
         address="Trung tâm xã Mường Pồn", lat=21.5335, lon=103.0790, capacity=300, kind="school"),
    dict(id="shl_mp2", commune_code="muong_pon", name="Nhà văn hoá bản Nậm Pồn",
         address="Bản Nậm Pồn, xã Mường Pồn", lat=21.5280, lon=103.0835, capacity=120, kind="community_hall"),
    dict(id="shl_mp3", commune_code="muong_pon", name="Điểm cao UBND xã (khu đồi sau trụ sở)",
         address="UBND xã Mường Pồn", lat=21.5312, lon=103.0808, capacity=200, kind="high_ground"),
    dict(id="shl_tc1", commune_code="tua_chua", name="Trường THPT Tủa Chùa",
         address="TT Tủa Chùa", lat=21.9915, lon=103.3585, capacity=400, kind="school"),
    dict(id="shl_tc2", commune_code="tua_chua", name="Nhà văn hoá huyện Tủa Chùa",
         address="TT Tủa Chùa", lat=21.9885, lon=103.3620, capacity=250, kind="community_hall"),
]


async def seed() -> dict:
    """Nạp dữ liệu mẫu (idempotent: xoá rồi nạp lại citizens/admins/shelters)."""
    async with session() as s:
        for model in (Citizen, Admin, Shelter):
            await s.execute(delete(model))
        for a in _SEED_ADMINS:
            s.add(Admin(**a))
        for c in _SEED_CITIZENS:
            s.add(Citizen(preferred_lang=_lang(c.get("ethnicity")), **c))
        for sh in _SEED_SHELTERS:
            s.add(Shelter(**sh))
    return {"admins": len(_SEED_ADMINS), "citizens": len(_SEED_CITIZENS),
            "shelters": len(_SEED_SHELTERS)}


# ----------------------------------------------------------------- truy vấn

async def citizens_by_commune(code: str) -> list[dict]:
    async with session() as s:
        rows = (await s.execute(select(Citizen).where(Citizen.commune_code == code))).scalars().all()
        return [_row(r) for r in rows]


async def admins_for_commune(code: str) -> list[dict]:
    async with session() as s:
        rows = (await s.execute(select(Admin))).scalars().all()
        return [_row(r) for r in rows if code in (r.communes or [])]


# --------------------------------------------------- Telegram: đăng ký người nhận

async def ensure_link_tokens(code: str) -> list[dict]:
    """Sinh telegram_link_token (nếu chưa có) cho từng công dân của xã. Trả danh sách
    {cccd, full_name, telegram_link_token} để tạo link đăng ký. KHÔNG lộ CCCD ra API."""
    async with session() as s:
        rows = (await s.execute(
            select(Citizen).where(Citizen.commune_code == code))).scalars().all()
        for c in rows:
            if not c.telegram_link_token:
                c.telegram_link_token = secrets.token_urlsafe(12)
        # commit tự động khi thoát context
        return [{"cccd": c.cccd, "full_name": c.full_name,
                 "telegram_link_token": c.telegram_link_token} for c in rows]


async def set_telegram_chat_id_by_token(token: str, chat_id: str) -> dict | None:
    """Gắn chat_id vào công dân sở hữu token. Trả công dân đã map, None nếu token lạ."""
    async with session() as s:
        row = (await s.execute(
            select(Citizen).where(Citizen.telegram_link_token == token))).scalar_one_or_none()
        if row is None:
            return None
        row.telegram_chat_id = str(chat_id)
        return {"cccd": row.cccd, "full_name": row.full_name,
                "telegram_chat_id": row.telegram_chat_id}


async def nearest_shelter(code: str, lat: float | None, lon: float | None) -> dict | None:
    async with session() as s:
        rows = (await s.execute(select(Shelter).where(Shelter.commune_code == code))).scalars().all()
    if not rows:
        return None
    if lat is None or lon is None:
        return _row(rows[0])
    best = min(rows, key=lambda sh: haversine_km(lat, lon, sh.lat, sh.lon))
    d = _row(best)
    d["distance_km"] = haversine_km(lat, lon, best.lat, best.lon)
    return d


async def nearest_for_commune(code: str, citizens: list[dict]) -> dict[str, dict]:
    """Nạp shelters của xã 1 LẦN, tính haversine gần nhất trong Python cho từng công
    dân (bỏ N+1: không query lại mỗi người)."""
    async with session() as s:
        shelters = (await s.execute(
            select(Shelter).where(Shelter.commune_code == code))).scalars().all()
    if not shelters:
        return {}
    out: dict[str, dict] = {}
    for c in citizens:
        lat, lon = c.get("lat"), c.get("lon")
        if lat is None or lon is None:
            continue
        best = min(shelters, key=lambda sh: haversine_km(lat, lon, sh.lat, sh.lon))
        d = _row(best)
        d["distance_km"] = haversine_km(lat, lon, best.lat, best.lon)
        out[c["cccd"]] = d
    return out


# -------------------------------------------------------------------- ghi

async def add_notification(payload: dict) -> dict:
    nid = "ntf_" + uuid.uuid4().hex[:10]
    async with session() as s:
        n = Notification(id=nid, **payload)
        s.add(n)
    return {"id": nid, **payload}


async def list_notifications(alert_id: str | None = None, cccd: str | None = None,
                             failed_only: bool = False) -> list[dict]:
    stmt = select(Notification)
    if alert_id:
        stmt = stmt.where(Notification.alert_id == alert_id)
    if cccd:
        stmt = stmt.where(Notification.cccd == cccd)
    if failed_only:
        stmt = stmt.where(Notification.status == "failed")
    async with session() as s:
        rows = (await s.execute(stmt.order_by(Notification.created_at.desc()))).scalars().all()
        return [_row(r) for r in rows]


async def add_home_visit(payload: dict) -> dict:
    hid = "hv_" + uuid.uuid4().hex[:10]
    async with session() as s:
        s.add(HomeVisit(id=hid, **payload))
    return {"id": hid, **payload}
