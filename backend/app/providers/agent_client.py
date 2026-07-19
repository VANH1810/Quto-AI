"""Client HTTP tới AI service (agent_worker, cổng 8100) — chế độ AGENT_MODE=remote.

Nhóm 5 (Cảnh báo) uỷ thác việc sinh + gửi bản tin cho agent_worker (LangGraph + Celery)
thay vì chạy AI nội bộ. agent-api là BẤT ĐỒNG BỘ: POST chỉ trả `warning_id`, kết quả có
sau qua `GET /warnings/{id}`. Client này POST rồi **poll** đến khi xong, map về `Alert`.

Ranh giới dữ liệu: agent_worker ghi notifications vào Postgres CỦA NÓ. Muốn nhóm 8
(/notifications) và FE thấy → trỏ DATABASE_URL của agent_worker vào cùng Supabase
(xem agent_worker/DEPLOY.md). Ở đây chỉ lưu bản thân Alert vào alerts_store để 5.2/5.3/5.4
đọc được.
"""

from __future__ import annotations

import asyncio
import logging
import time
from datetime import datetime

import httpx

from app.config import get_settings
from app.schemas.alert import Alert, AlertStatus, BulletinText, HazardEvent

log = logging.getLogger("app.agent_client")

# Trạng thái CUỐI của job quét (agent đã xong phần AI) và của bước duyệt (resume).
_TERMINAL_SCAN = {"pending_approval", "no_risk", "dispatching", "sent", "done", "rejected", "failed"}
_TERMINAL_RESUME = {"dispatching", "rejected", "failed"}

# agent status (chuỗi) → AlertStatus của backend.
_STATUS_MAP = {
    "pending_approval": AlertStatus.pending_approval,
    "dispatching": AlertStatus.dispatching,
    "approved": AlertStatus.approved,
    "rejected": AlertStatus.rejected,
    "sent": AlertStatus.sent,
    "no_risk": AlertStatus.detected,
}


def _now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _base_url() -> str:
    url = get_settings().agent_base_url.rstrip("/")
    if not url:
        raise RuntimeError("AGENT_MODE=remote nhưng chưa đặt AGENT_BASE_URL (vd http://<IP-VM>:8100).")
    return url


async def _post(path: str, json: dict) -> dict:
    timeout = get_settings().agent_timeout_seconds
    async with httpx.AsyncClient(timeout=timeout) as client:
        r = await client.post(f"{_base_url()}{path}", json=json)
        r.raise_for_status()
        return r.json()


async def _get(path: str) -> dict:
    async with httpx.AsyncClient(timeout=15) as client:
        r = await client.get(f"{_base_url()}{path}")
        r.raise_for_status()
        return r.json()


async def _poll(warning_id: str, terminal: set[str]) -> dict:
    """Poll GET /warnings/{id} đến khi `status` là trạng thái CUỐI (hoặc hết thời gian).

    Agent chạy bất đồng bộ (Celery): POST chỉ trả warning_id, kết quả có sau qua GET.
    Backoff 1→5s; chặn tổng thời gian < agent_timeout_seconds. Trả snapshot cuối đọc được.
    """
    deadline = time.monotonic() + max(10.0, get_settings().agent_timeout_seconds - 5)
    delay, last = 1.0, {}
    while time.monotonic() < deadline:
        await asyncio.sleep(delay)
        try:
            last = await _get(f"/warnings/{warning_id}")
        except Exception as e:  # noqa: BLE001 — lỗi mạng tạm thời → thử lại
            log.warning("poll %s lỗi: %s", warning_id, e)
            delay = min(delay + 1.0, 5.0)
            continue
        if last.get("status") in terminal:
            return last
        delay = min(delay + 1.0, 5.0)
    return last


def _to_alert(res: dict) -> Alert | None:
    """Map kết quả agent-api → Alert. Trả None nếu không có rủi ro (no_risk)."""
    top = res.get("top_event")
    if not top:
        return None
    event = HazardEvent(**top)
    if res.get("actions") and not event.recommended_actions:
        event.recommended_actions = list(res["actions"])
    bulletins = [BulletinText(**b) for b in res.get("bulletins", [])]
    status = _STATUS_MAP.get(res.get("status", ""), AlertStatus.detected)
    n = res.get("n_recipients")
    return Alert(
        id=res.get("warning_id") or res.get("alert_id") or "alt_remote",
        event=event, status=status, bulletins=bulletins, created_at=_now(),
        audit=[{"step": "agent", "detail": f"agent_worker · {res.get('status')}"
                + (f" · {n} người nhận" if n is not None else "")}],
    )


# --------------------------------------------------------------------- public

async def submit_alert(commune_code: str, langs: list[str] | None = None) -> dict:
    """POST /warnings — đẩy job cho agent, TRẢ NGAY {warning_id, status} (KHÔNG poll).

    Backend dùng để bất đồng bộ: trả warning_id cho FE poll qua scan_status().
    """
    res = await _post("/warnings", {
        "commune_code": commune_code,
        "langs": langs or ["vi", "tai", "hmn"],
        "trigger": "backend_scan",
    })
    wid = res.get("warning_id")
    if not wid:
        raise RuntimeError(f"agent /warnings không trả warning_id: {res}")
    return {"warning_id": wid, "status": res.get("status", "queued")}


async def scan_status(warning_id: str) -> dict:
    """GET /warnings/{id} (1 lần) → envelope ĐẦY ĐỦ: state/status/progress/metadata/alert.

    Forward NGUYÊN VẸN từ agent:
    - `state`   : PENDING|PROGRESS|SUCCESS|FAILURE (Celery).
    - `status`  : queued|running|pending_approval|dispatching|no_risk|rejected|failed.
    - `progress`: {node, step, total} khi đang chạy (đọc được cả lúc PROGRESS).
    - `metadata`: kết quả AI (risk_level, needs_human, n_recipients, actions, bulletins,
                  top_event, alert_id) — tích luỹ ngay cả khi CHƯA xong.
    - `alert`   : Alert đã map (typed) khi có nguy cơ + đã xong; None nếu no_risk/lỗi.
    """
    snap = await _get(f"/warnings/{warning_id}")
    status = snap.get("status")
    done = status in _TERMINAL_SCAN
    result = snap.get("result") or {}
    resume_info = (snap.get("resume") or {}).get("info") or {}    # kết quả bước duyệt (dispatch)
    alert = None
    if done and status not in ("no_risk", "failed", "rejected") and result.get("top_event"):
        alert = _to_alert({**result, "warning_id": warning_id, "status": status})
    return {
        "state": snap.get("state"),
        "status": status,
        "done": done,
        "progress": snap.get("progress"),
        "risk_level": result.get("risk_level"),
        "commune_code": result.get("commune_code"),
        "metadata": result or None,
        "alert": alert,
        "dispatched": resume_info.get("dispatched"),     # số tin đã gửi (sau approve)
        "approved_by": resume_info.get("approved_by"),
    }


async def create_alert(commune_code: str, langs: list[str] | None = None) -> Alert | None:
    """(Giữ tương thích) POST /warnings + POLL đến khi xong → Alert | None (no_risk)."""
    ticket = await submit_alert(commune_code, langs)
    final = await _poll(ticket["warning_id"], _TERMINAL_SCAN)
    status = final.get("status")
    if status == "no_risk":
        return None
    if status in (None, "queued", "running"):
        raise RuntimeError(f"agent job {ticket['warning_id']} chưa xong sau timeout.")
    if status == "failed":
        raise RuntimeError(f"agent job {ticket['warning_id']} thất bại.")
    return _to_alert({**(final.get("result") or {}), "warning_id": ticket["warning_id"], "status": status})


async def submit_approve(warning_id: str, admin_id: str, edited_body_vi: str | None) -> dict:
    """POST /warnings/{id}/approve — TRẢ NGAY {warning_id, status} (KHÔNG poll).

    FE poll `GET /alerts/scan/{warning_id}` để xem tiến trình gửi (dispatching → done + dispatched).
    """
    res = await _post(f"/warnings/{warning_id}/approve", {
        "admin_id": admin_id, "edited_body_vi": edited_body_vi,
    })
    return {"warning_id": warning_id, "status": res.get("status", "approving")}


async def submit_reject(warning_id: str, admin_id: str, note: str | None) -> dict:
    """POST /warnings/{id}/reject — TRẢ NGAY {warning_id, status} (KHÔNG poll)."""
    res = await _post(f"/warnings/{warning_id}/reject", {"admin_id": admin_id, "note": note})
    return {"warning_id": warning_id, "status": res.get("status", "rejecting")}
