"""Helper chạy graph (async) cho Celery task gọi, + dựng kế hoạch dispatch.

Không còn interrupt/resume trong graph: graph kết thúc sau human_gate. tasks.py:
- cấp thấp → dispatch ngay; cấp cao → chờ duyệt rồi mới dispatch.
"""

from __future__ import annotations

from agent_worker.config import get_worker_settings
from agent_worker.graph import agent_tools, nodes
from agent_worker.graph.build import get_graph
from agent_worker.infra.messages import AgentJobRequest, DispatchMessage

_RECURSION_LIMIT = 25   # trần số vòng model⇄tool (an toàn, đủ cho 5 tool)


def primary_channel(recipient: dict) -> str:
    """Kênh chính 1 người: Telegram nếu đã đăng ký (có chat_id), không thì loa (công cộng)."""
    if recipient.get("telegram_chat_id"):
        return "telegram"
    return "loudspeaker"


async def run_graph(payload: dict, progress_cb=None) -> dict:
    """Chạy AGENT tool-calling cho 1 job, trả state cuối (shape như pipeline cũ).

    Agent tự gọi tool (nghiệp vụ giữ nguyên); artifact ghi vào run_ctx. Sau khi agent xong,
    `_finalize` dựng state + chạy cổng duyệt (human_gate) tất định. progress_cb → Celery.
    """
    req = AgentJobRequest(**payload)
    if progress_cb is not None:
        nodes.progress_hook.set(progress_cb)
    nodes.progress_state.set({})   # accumulator result tích luỹ theo tool
    agent_tools.run_ctx.set({
        "run_id": req.job_id, "job_id": req.job_id, "commune_code": req.commune_code,
        "commune": req.commune,    # tool dùng thẳng nếu có; None → geo_tool
        "langs": req.langs, "trigger": req.trigger, "forecast": req.forecast,
    })
    task = (f"Quét nguy cơ thiên tai và soạn cảnh báo cho xã có mã '{req.commune_code}'. "
            f"Ngôn ngữ cần có: {', '.join(req.langs)}. Làm theo đúng quy trình công cụ.")
    await get_graph().ainvoke(
        {"messages": [{"role": "user", "content": task}]},
        config={"recursion_limit": _RECURSION_LIMIT},
    )
    return _finalize()


def _finalize() -> dict:
    """Đọc run_ctx → dựng state cuối + human_gate tất định (agent KHÔNG tự quyết gửi)."""
    ctx = agent_tools.run_ctx.get() or {}
    top = ctx.get("top_event")
    state = {
        "job_id": ctx.get("job_id"), "commune_code": ctx.get("commune_code"),
        "alert_id": ctx.get("alert_id"), "top_event": top,
        "risk_level": ctx.get("risk_level", 0), "actions": ctx.get("actions", []),
        "recipients": ctx.get("recipients", {}), "bulletins": ctx.get("bulletins", []),
        "payloads": ctx.get("payloads", []),
    }
    if not top:                                   # không có nguy cơ → dừng, không gửi
        state["needs_human"] = False
        state["status"] = "no_risk"
        return state
    threshold = get_worker_settings().human_approval_min_level
    needs = int(state["risk_level"]) >= threshold
    state["needs_human"] = needs
    state["status"] = "pending_approval" if needs else "approved"
    nodes._record(needs_human=needs, status=state["status"])
    nodes._emit("finalize")
    return state


def build_dispatch_messages(values: dict) -> list[dict]:
    """Từ state (payloads) → danh sách DispatchMessage (chọn kênh theo người nhận)."""
    top = values.get("top_event") or {}
    out: list[dict] = []
    for p in values.get("payloads", []):
        channel = primary_channel(p["recipient"])
        out.append(DispatchMessage(
            job_id=values["job_id"], alert_id=values.get("alert_id"),
            channel=channel, commune_code=values["commune_code"],
            commune_name=top.get("commune_name", ""),
            recipient=p["recipient"], lang=p["lang"],
            title=p["title"], body=p["body"],
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
