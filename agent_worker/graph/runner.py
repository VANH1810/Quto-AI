"""Helper chạy graph (async) cho Celery task gọi, + dựng kế hoạch dispatch.

Không còn interrupt/resume trong graph: graph kết thúc sau human_gate. tasks.py:
- cấp thấp → dispatch ngay; cấp cao → chờ duyệt rồi mới dispatch.
"""

from __future__ import annotations

from agent_worker.graph import nodes
from agent_worker.graph.build import get_graph
from agent_worker.infra.messages import AgentJobRequest, DispatchMessage


def primary_channel(recipient: dict) -> str:
    """Kênh chính 1 người: Zalo nếu có consent + SĐT, không thì loa (công cộng)."""
    if recipient.get("consent_zalo_sms") and recipient.get("phone"):
        return "zalo_zns"
    return "loudspeaker"


async def run_graph(payload: dict, progress_cb=None) -> dict:
    """Chạy graph cho 1 job, trả state cuối (bulletins, zalo_payloads, needs_human...).

    progress_cb(node_name) được gọi mỗi khi vào 1 node (để Celery update_state).
    """
    req = AgentJobRequest(**payload)
    if progress_cb is not None:
        nodes.progress_hook.set(progress_cb)
    state = {
        "job_id": req.job_id, "run_id": req.job_id, "commune_code": req.commune_code,
        "langs": req.langs, "trigger": req.trigger, "forecast": req.forecast,
    }
    return await get_graph().ainvoke(state)


def build_dispatch_messages(values: dict) -> list[dict]:
    """Từ state (zalo_payloads) → danh sách DispatchMessage (chọn kênh theo consent)."""
    top = values.get("top_event") or {}
    out: list[dict] = []
    for p in values.get("zalo_payloads", []):
        channel = primary_channel(p["recipient"])
        out.append(DispatchMessage(
            job_id=values["job_id"], alert_id=values.get("alert_id"),
            channel=channel, commune_code=values["commune_code"],
            commune_name=top.get("commune_name", ""),
            recipient=p["recipient"], lang=p["lang"],
            title=p["title"], body=p["body"],
            zalo_template=p.get("zalo_template"),
            nearest_shelter=p.get("nearest_shelter"),
        ).model_dump())
    return out


def summarize(values: dict) -> dict:
    """Kết quả rút gọn để trả trong Celery result (polling đọc được)."""
    return {
        "status": values.get("status"),
        "commune_code": values.get("commune_code"),
        "risk_level": values.get("risk_level"),
        "needs_human": values.get("needs_human", False),
        "top_event": values.get("top_event"),
        "actions": values.get("actions", []),
        "bulletins": values.get("bulletins", []),
        "alert_id": values.get("alert_id"),
        "n_recipients": len((values.get("recipients") or {}).get("citizens", [])),
    }
