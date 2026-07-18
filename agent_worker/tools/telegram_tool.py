"""Tool gửi cảnh báo qua Telegram Bot API — thật (httpx) + mock cho demo.

TELEGRAM_PROVIDER=mock (mặc định) hoặc thiếu token: mô phỏng gửi thành công (không gọi mạng).
TELEGRAM_PROVIDER=live + có TELEGRAM_BOT_TOKEN: gọi Bot API thật.

Ràng buộc Telegram: bot CHỈ nhắn được cho người đã Start bot trước (đã có chat_id).
Việc lấy chat_id (onboarding) qua get_updates() + link t.me/<bot>?start=<token>.
"""

from __future__ import annotations

import logging

import httpx

from agent_worker.config import get_worker_settings
from agent_worker.shared.alert import DispatchRecord, DispatchStatus

log = logging.getLogger("agent_worker.telegram")

_API = "https://api.telegram.org/bot{token}/{method}"


def _live() -> bool:
    s = get_worker_settings()
    return s.telegram_provider.lower() == "live" and bool(s.telegram_bot_token)


async def _call(method: str, payload: dict) -> dict:
    """Gọi 1 method Bot API. Trả JSON Telegram ({ok, result|description})."""
    token = get_worker_settings().telegram_bot_token
    url = _API.format(token=token, method=method)
    async with httpx.AsyncClient(timeout=15) as c:
        r = await c.post(url, json=payload)
    try:
        return r.json()
    except Exception:  # noqa: BLE001
        return {"ok": False, "description": r.text[:200]}


async def send_message(chat_id: str, text: str) -> DispatchRecord:
    """Gửi 1 tin tới 1 chat_id (dùng cho endpoint test và dispatch)."""
    if not chat_id:
        return DispatchRecord(channel="telegram", target="", recipients=1, delivered=0,
                              status=DispatchStatus.failed, detail="Thiếu chat_id")
    if not _live():
        return DispatchRecord(channel="telegram", target=str(chat_id), recipients=1, delivered=1,
                              status=DispatchStatus.ok, detail="[mock] Đã gửi Telegram")
    j = await _call("sendMessage", {"chat_id": chat_id, "text": text, "parse_mode": "HTML"})
    ok = bool(j.get("ok"))
    if not ok:
        log.warning("Telegram sendMessage fail chat=%s: %s", chat_id, j.get("description"))
    return DispatchRecord(
        channel="telegram", target=str(chat_id), recipients=1, delivered=1 if ok else 0,
        status=DispatchStatus.ok if ok else DispatchStatus.failed,
        detail="Telegram OK" if ok else f"Telegram lỗi: {j.get('description', '')[:120]}",
    )


async def send_raw(token: str, chat_id: str, text: str) -> DispatchRecord:
    """Gửi tin qua MỘT token bot chỉ định (dùng cho endpoint demo với bot thứ 2).

    Luôn gọi Bot API thật nếu có token + chat_id (không phụ thuộc TELEGRAM_PROVIDER).
    """
    if not token or not chat_id:
        return DispatchRecord(channel="telegram", target=str(chat_id or ""), recipients=1,
                              delivered=0, status=DispatchStatus.failed,
                              detail="Thiếu token hoặc chat_id")
    url = _API.format(token=token, method="sendMessage")
    async with httpx.AsyncClient(timeout=15) as c:
        r = await c.post(url, json={"chat_id": chat_id, "text": text, "parse_mode": "HTML"})
    try:
        j = r.json()
    except Exception:  # noqa: BLE001
        j = {"ok": False, "description": r.text[:200]}
    ok = bool(j.get("ok"))
    if not ok:
        log.warning("Telegram(bot2) sendMessage fail chat=%s: %s", chat_id, j.get("description"))
    return DispatchRecord(
        channel="telegram", target=str(chat_id), recipients=1, delivered=1 if ok else 0,
        status=DispatchStatus.ok if ok else DispatchStatus.failed,
        detail="Telegram OK" if ok else f"Telegram lỗi: {j.get('description', '')[:150]}",
    )


async def send(recipient: dict, title: str, body: str) -> DispatchRecord:
    """Gửi cảnh báo cho 1 người nhận (đọc chat_id từ recipient)."""
    chat_id = recipient.get("telegram_chat_id")
    name = recipient.get("full_name", "")
    if not chat_id:
        return DispatchRecord(channel="telegram", target=name, recipients=1, delivered=0,
                              status=DispatchStatus.failed, detail="Chưa đăng ký Telegram (không có chat_id)")
    text = f"<b>{title}</b>\n{body}" if title else body
    rec = await send_message(str(chat_id), text)
    rec.target = name or rec.target
    return rec


async def get_updates() -> list[dict]:
    """Lấy update gần đây → [{chat_id, name, start_payload, text}]. Dùng để onboarding.

    start_payload = tham số sau '/start ' (token đăng ký), nếu có.
    """
    if not _live():
        return []
    j = await _call("getUpdates", {"allowed_updates": ["message"], "limit": 100})
    out: list[dict] = []
    for u in j.get("result", []):
        msg = u.get("message") or {}
        chat = msg.get("chat") or {}
        chat_id = chat.get("id")
        if chat_id is None:
            continue
        text = msg.get("text", "") or ""
        start_payload = None
        if text.startswith("/start"):
            parts = text.split(maxsplit=1)
            start_payload = parts[1].strip() if len(parts) > 1 else None
        name = " ".join(x for x in [chat.get("first_name"), chat.get("last_name")] if x) \
            or chat.get("username") or ""
        out.append({"chat_id": str(chat_id), "name": name,
                    "start_payload": start_payload, "text": text})
    return out


async def get_me() -> dict:
    """Thông tin bot (để lấy username dựng link t.me/<username>?start=...)."""
    if not _live():
        return {"ok": False, "description": "TELEGRAM_PROVIDER != live hoặc thiếu token"}
    return await _call("getMe", {})
