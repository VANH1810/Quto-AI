"""Celery task cho các tác vụ AI (background) — chạy trên broker/backend Redis.

- agent.run_job      : chạy graph (gồm LLM compose) → bulletins + quyết định human-loop.
- agent.resume_job   : cán bộ duyệt/bác → fan-out dispatch.
- agent.dispatch_message : gửi 1 bản tin tới 1 người (Telegram/loa) + retry + đến-tận-nhà.

Polling: AsyncResult(job_id).state + .info (PROGRESS meta {node}) / .result (kết quả).
Async code chạy trên 1 event loop bền/1 process (run_async) để engine/redis không lỗi loop.
"""

from __future__ import annotations

import asyncio
import logging
import threading

from agent_worker.celery_app import app
from agent_worker.config import get_worker_settings
from agent_worker.graph import runner
from agent_worker.infra.db import init_models
from agent_worker.infra.messages import (AgentControlCommand, AgentJobRequest,
                                         DispatchMessage)
from agent_worker import repo, data_repo
from agent_worker.tools import speaker_tool, telegram_tool

log = logging.getLogger("agent_worker.tasks")

_loops = threading.local()          # event loop RIÊNG mỗi thread (Celery threads pool)
_db_ready = False
_db_lock = threading.Lock()


def run_async(coro):
    """Chạy coroutine trên event loop riêng của THREAD hiện tại.

    Celery threads pool: mỗi task chạy trong 1 thread → mỗi thread giữ 1 loop bền
    (asyncpg/engine gắn theo loop). Không dùng loop global (sẽ vỡ khi đa thread).
    """
    loop = getattr(_loops, "loop", None)
    if loop is None or loop.is_closed():
        loop = asyncio.new_event_loop()
        _loops.loop = loop
        asyncio.set_event_loop(loop)
    return loop.run_until_complete(coro)


def _ensure_db() -> None:
    """Tạo bảng 1 lần/process (idempotent). Chạy trên loop của thread gọi đầu tiên."""
    global _db_ready
    if _db_ready:
        return
    with _db_lock:
        if not _db_ready:
            run_async(init_models())
            _db_ready = True


# --------------------------------------------------------------- run agent job

@app.task(bind=True, name="agent.run_job")
def run_agent_job(self, payload: dict) -> dict:
    _ensure_db()
    req = AgentJobRequest(**payload)

    def progress(meta: dict) -> None:
        # meta = {node, step, total, result(tích luỹ)} do nodes._emit gửi lên
        self.update_state(state="PROGRESS", meta={"job_id": req.job_id, **meta})

    return run_async(_run_job(req, payload, progress))


async def _run_job(req: AgentJobRequest, payload: dict, progress) -> dict:
    log.info("▶️  job %s BẮT ĐẦU — xã=%s, langs=%s, trigger=%s",
             req.job_id, req.commune_code, ",".join(req.langs), req.trigger)
    await repo.save_run(req.job_id, commune_code=req.commune_code, trigger=req.trigger,
                        langs=req.langs, llm_provider="")
    try:
        values = await runner.run_graph(payload, progress_cb=progress)
    except Exception as e:  # noqa: BLE001
        await repo.update_run_status(req.job_id, "failed", error=str(e), finished=True)
        raise

    summary = runner.summarize(values)
    n_rcpt = summary.get("n_recipients", 0)
    if not values.get("top_event"):                      # không có rủi ro
        await repo.update_run_status(req.job_id, "no_risk", finished=True)
        log.info("✅ job %s [%s]: KHÔNG có nguy cơ → no_risk (không gửi)",
                 req.job_id, req.commune_code)
        return {**summary, "status": "no_risk"}

    messages = runner.build_dispatch_messages(values)
    await repo.update_run_status(req.job_id, values.get("status", "approved"),
                                 risk_level=values.get("risk_level"),
                                 alert_id=values.get("alert_id"))

    if values.get("needs_human"):                        # cấp cao → BÁO ADMIN rồi chờ duyệt
        await _notify_admins(req, values)
        log.info("✅ job %s [%s]: cấp %s → PENDING_APPROVAL, %d tin chờ duyệt (đã báo admin)",
                 req.job_id, req.commune_code, summary.get("risk_level"), len(messages))
        return {**summary, "status": "pending_approval", "dispatch_plan": messages}

    # cấp thấp → gửi ngay (fan-out Celery task)
    for m in messages:
        dispatch_message.apply_async(args=[m])
    await repo.update_run_status(req.job_id, "dispatching", finished=True)
    log.info("✅ job %s [%s]: cấp %s → DISPATCHING %d tin (%d người nhận)",
             req.job_id, req.commune_code, summary.get("risk_level"), len(messages), n_rcpt)
    return {**summary, "status": "dispatching", "dispatched": len(messages)}


async def _notify_admins(req: AgentJobRequest, values: dict) -> None:
    """Báo cán bộ xã có cảnh báo CHỜ DUYỆT (trước khi gửi dân). Ghi notification;
    gửi kèm Telegram nếu admin đã có telegram_chat_id. Lỗi báo admin KHÔNG chặn luồng."""
    top = values.get("top_event") or {}
    admins = (values.get("recipients") or {}).get("admins", [])
    detail = (f"Cảnh báo {top.get('hazard', '')} cấp {values.get('risk_level')} tại "
              f"{top.get('commune_name', req.commune_code)} — CHỜ DUYỆT để gửi người dân.")
    for a in admins:
        try:
            await data_repo.add_notification({
                "alert_id": values.get("alert_id"), "cccd": a.get("id"),
                "full_name": a.get("full_name"), "commune_code": req.commune_code,
                "channel": "admin_review", "lang": "vi",
                "status": "pending_approval", "detail": detail,
            })
            if a.get("telegram_chat_id"):
                await telegram_tool.send_message(str(a["telegram_chat_id"]),
                                                 f"🛂 <b>Chờ duyệt</b>\n{detail}")
        except Exception as e:  # noqa: BLE001
            log.warning("Báo admin lỗi (%s): %s", a.get("id"), e)


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


async def _record_notif(payload: dict) -> None:
    """Ghi notification vào Postgres local (best-effort — KHÔNG để lỗi ghi làm gãy/duplicate gửi)."""
    try:
        await data_repo.add_notification(payload)
    except Exception as e:  # noqa: BLE001
        log.warning("Ghi notification lỗi: %s", e)


async def _dispatch(payload: dict) -> dict:
    msg = DispatchMessage(**payload)
    settings = get_worker_settings()

    if msg.channel == "telegram":
        record = await telegram_tool.send(msg.recipient, msg.title, msg.body)
    else:  # loudspeaker — phát loa công cộng (mock)
        record = await speaker_tool.send(msg.channel, msg.commune_code, msg.recipient,
                                         msg.title, msg.body, None, msg.attempt)
    if record.status.value != "failed":
        await _record_notif(_notif(msg, "sent", record.detail))
        return {"status": "sent", "channel": msg.channel, "to": msg.recipient.get("full_name")}

    # thất bại: còn lượt → re-enqueue (countdown) ; hết lượt → failed + đến tận nhà
    if msg.attempt + 1 < settings.dispatch_max_retry:
        msg.attempt += 1
        dispatch_message.apply_async(args=[msg.model_dump()], countdown=5)
        return {"status": "retry", "attempt": msg.attempt, "channel": msg.channel}

    await _record_notif(
        _notif(msg, "failed",
               f"{record.detail} (hết {settings.dispatch_max_retry} lượt — cần đến tận nhà)"))
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
