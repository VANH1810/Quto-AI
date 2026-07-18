"""Celery task cho các tác vụ AI (background) — chạy trên broker/backend Redis.

- agent.run_job      : chạy graph (gồm LLM compose) → bulletins + quyết định human-loop.
- agent.resume_job   : cán bộ duyệt/bác → fan-out dispatch.
- agent.dispatch_message : gửi 1 bản tin tới 1 người (Zalo/SMS/loa) + retry + đến-tận-nhà.

Polling: AsyncResult(job_id).state + .info (PROGRESS meta {node}) / .result (kết quả).
Async code chạy trên 1 event loop bền/1 process (run_async) để engine/redis không lỗi loop.
"""

from __future__ import annotations

import asyncio
import logging

from agent_worker.celery_app import app
from agent_worker.config import get_worker_settings
from agent_worker.graph import runner
from agent_worker.infra.db import init_models
from agent_worker.infra.messages import (AgentControlCommand, AgentJobRequest,
                                         DispatchMessage)
from agent_worker import repo
from agent_worker.tools import user_api_tool, zalo_tool

log = logging.getLogger("agent_worker.tasks")

_loop: asyncio.AbstractEventLoop | None = None
_db_ready = False


def run_async(coro):
    """Chạy coroutine trên 1 event loop bền theo process (an toàn cho engine async)."""
    global _loop
    if _loop is None or _loop.is_closed():
        _loop = asyncio.new_event_loop()
        asyncio.set_event_loop(_loop)
    return _loop.run_until_complete(coro)


def _ensure_db() -> None:
    global _db_ready
    if not _db_ready:
        run_async(init_models())
        _db_ready = True


# --------------------------------------------------------------- run agent job

@app.task(bind=True, name="agent.run_job")
def run_agent_job(self, payload: dict) -> dict:
    _ensure_db()
    req = AgentJobRequest(**payload)

    def progress(node: str) -> None:
        self.update_state(state="PROGRESS", meta={"job_id": req.job_id, "node": node})

    return run_async(_run_job(req, payload, progress))


async def _run_job(req: AgentJobRequest, payload: dict, progress) -> dict:
    await repo.save_run(req.job_id, commune_code=req.commune_code, trigger=req.trigger,
                        langs=req.langs, llm_provider="")
    try:
        values = await runner.run_graph(payload, progress_cb=progress)
    except Exception as e:  # noqa: BLE001
        await repo.update_run_status(req.job_id, "failed", error=str(e), finished=True)
        raise

    summary = runner.summarize(values)
    if not values.get("top_event"):                      # không có rủi ro
        await repo.update_run_status(req.job_id, "no_risk", finished=True)
        return {**summary, "status": "no_risk"}

    messages = runner.build_dispatch_messages(values)
    await repo.update_run_status(req.job_id, values.get("status", "approved"),
                                 risk_level=values.get("risk_level"),
                                 alert_id=values.get("alert_id"))

    if values.get("needs_human"):                        # cấp cao → chờ duyệt
        return {**summary, "status": "pending_approval", "dispatch_plan": messages}

    # cấp thấp → gửi ngay (fan-out Celery task)
    for m in messages:
        dispatch_message.apply_async(args=[m])
    await repo.update_run_status(req.job_id, "dispatching", finished=True)
    return {**summary, "status": "dispatching", "dispatched": len(messages)}


# --------------------------------------------------------------- resume (duyệt)

@app.task(bind=True, name="agent.resume_job")
def resume_agent_job(self, payload: dict) -> dict:
    _ensure_db()
    cmd = AgentControlCommand(**payload)
    return run_async(_resume_job(cmd))


async def _resume_job(cmd: AgentControlCommand) -> dict:
    if cmd.action == "reject":
        await repo.update_run_status(cmd.job_id, "rejected", finished=True)
        return {"status": "rejected", "by": cmd.admin_id}

    # lấy dispatch_plan từ kết quả của run_job
    res = app.AsyncResult(cmd.job_id).result or {}
    messages = list(res.get("dispatch_plan", []))
    if cmd.edited_body_vi:                                # admin sửa nội dung tiếng Việt
        for m in messages:
            if m.get("lang") == "vi":
                m["body"] = cmd.edited_body_vi

    for m in messages:
        dispatch_message.apply_async(args=[m])
    await repo.update_run_status(cmd.job_id, "dispatching", finished=True)
    return {"status": "dispatching", "dispatched": len(messages), "approved_by": cmd.admin_id}


# --------------------------------------------------------------- dispatch 1 tin

@app.task(bind=True, name="agent.dispatch_message")
def dispatch_message(self, payload: dict) -> dict:
    return run_async(_dispatch(payload))


async def _dispatch(payload: dict) -> dict:
    msg = DispatchMessage(**payload)
    settings = get_worker_settings()

    record = await zalo_tool.send(msg.channel, msg.commune_code, msg.recipient,
                                  msg.title, msg.body, msg.zalo_template, msg.attempt)
    if record.status.value != "failed":
        await user_api_tool.create_notification(_notif(msg, "sent", record.detail))
        return {"status": "sent", "channel": msg.channel, "to": msg.recipient.get("full_name")}

    # thất bại: còn lượt → re-enqueue (countdown) ; hết lượt → failed + đến tận nhà
    if msg.attempt + 1 < settings.dispatch_max_retry:
        msg.attempt += 1
        dispatch_message.apply_async(args=[msg.model_dump()], countdown=5)
        return {"status": "retry", "attempt": msg.attempt, "channel": msg.channel}

    await user_api_tool.create_notification(
        _notif(msg, "failed", f"{record.detail} (hết {settings.dispatch_max_retry} lượt)"))
    try:
        admins = await user_api_tool.admins_for_commune(msg.commune_code)
        assigned = admins[0]["id"] if admins else None
        await user_api_tool.create_home_visit({
            "alert_id": msg.alert_id or "alt_unknown", "commune_code": msg.commune_code,
            "assigned_admin_id": assigned,
            "reason": f"Gửi {msg.channel} lỗi tới {msg.recipient.get('full_name')}: {record.detail}",
        })
    except Exception as e:  # noqa: BLE001
        log.warning("Không tạo được home-visit: %s", e)
    return {"status": "failed", "channel": msg.channel, "to": msg.recipient.get("full_name")}


def _notif(msg: DispatchMessage, status: str, detail: str) -> dict:
    r, sh = msg.recipient, (msg.nearest_shelter or {})
    return {
        "alert_id": msg.alert_id or "alt_unknown", "cccd": r.get("cccd", ""),
        "full_name": r.get("full_name", ""), "address": r.get("address", ""),
        "commune_code": msg.commune_code, "channel": msg.channel, "lang": msg.lang,
        "status": status, "nearest_shelter_id": sh.get("id"),
        "nearest_shelter_name": sh.get("name"), "nearest_shelter_address": sh.get("address"),
        "nearest_shelter_km": sh.get("distance_km"), "detail": detail,
    }
