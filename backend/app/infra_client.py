"""Client Celery mỏng cho backend — gửi task cho AI Agent worker + đọc trạng thái.

Backend KHÔNG import agent_worker (tránh kéo langgraph vào API). Gửi task theo TÊN
qua Celery (broker RabbitMQ), đọc kết quả/metadata từ Redis result backend qua
AsyncResult → phục vụ BackEnd Services polling.
"""

from __future__ import annotations

from celery import Celery
from celery.result import AsyncResult

from app.config import get_settings

_s = get_settings()
celery_client = Celery("quto_agent_client", broker=_s.rabbitmq_url, backend=_s.redis_url)


def submit_job(payload: dict, job_id: str) -> None:
    celery_client.send_task("agent.run_job", args=[payload], task_id=job_id, queue="agent")


def submit_control(payload: dict, job_id: str) -> None:
    celery_client.send_task("agent.resume_job", args=[payload],
                            task_id=f"{job_id}:resume", queue="agent")


def _snapshot(ar: AsyncResult) -> dict:
    state = ar.state
    info = ar.info
    if isinstance(info, BaseException):          # FAILURE → info là exception
        info = {"error": str(info)}
    return {"state": state, "info": info}


def poll(job_id: str) -> dict:
    run = AsyncResult(job_id, app=celery_client)
    resume = AsyncResult(f"{job_id}:resume", app=celery_client)
    run_snap = _snapshot(run)
    resume_snap = _snapshot(resume) if resume.state != "PENDING" else None

    # Trạng thái tổng hợp cho BackEnd Services đọc nhanh.
    if resume_snap and resume_snap["state"] == "SUCCESS":
        status = (resume_snap["info"] or {}).get("status", "dispatching")
    elif run_snap["state"] == "SUCCESS":
        status = (run_snap["info"] or {}).get("status", "done")
    elif run_snap["state"] == "PROGRESS":
        status = "running"
    elif run_snap["state"] == "FAILURE":
        status = "failed"
    else:
        status = "queued"                        # PENDING = chưa/đang chờ worker

    return {"job_id": job_id, "status": status, "run": run_snap, "resume": resume_snap}
