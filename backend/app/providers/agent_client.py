"""Client HTTP tới AI service (agent_worker, cổng 8100) — chế độ AGENT_MODE=remote.

Nhóm 5 (Cảnh báo) uỷ thác việc sinh + gửi bản tin cho agent_worker (LangGraph + Celery)
thay vì chạy AI nội bộ. agent-api thiết kế "gọi 1 lần có kết quả" (đồng bộ), nên map
thẳng kết quả về schema `Alert` của backend để FE giữ nguyên hợp đồng.

Ranh giới dữ liệu: agent_worker ghi notifications vào Postgres CỦA NÓ. Muốn nhóm 8
(/notifications) và FE thấy → trỏ DATABASE_URL của agent_worker vào cùng Supabase
(xem agent_worker/DEPLOY.md). Ở đây chỉ lưu bản thân Alert vào alerts_store để 5.2/5.3/5.4
đọc được.
"""

from __future__ import annotations

from datetime import datetime

import httpx

from app.config import get_settings
from app.schemas.alert import Alert, AlertStatus, BulletinText, HazardEvent

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

async def create_alert(commune_code: str, langs: list[str] | None = None) -> Alert | None:
    """POST /warnings — AI quét nguy cơ + sinh bản tin đa ngữ (đồng bộ)."""
    res = await _post("/warnings", {
        "commune_code": commune_code,
        "langs": langs or ["vi", "tai", "hmn"],
        "trigger": "backend_scan",
    })
    res.setdefault("warning_id", res.get("warning_id"))
    return _to_alert(res)


async def approve(warning_id: str, admin_id: str, edited_body_vi: str | None) -> dict:
    """POST /warnings/{id}/approve — cán bộ duyệt → agent fan-out dispatch."""
    return await _post(f"/warnings/{warning_id}/approve", {
        "admin_id": admin_id, "edited_body_vi": edited_body_vi,
    })


async def reject(warning_id: str, admin_id: str, note: str | None) -> dict:
    """POST /warnings/{id}/reject — cán bộ bác bỏ."""
    return await _post(f"/warnings/{warning_id}/reject", {"admin_id": admin_id, "note": note})
