"""Celery app — broker = RabbitMQ (điều phối tin cậy), result backend = Redis (polling).

Chạy worker:
  celery -A agent_worker.celery_app worker -Q agent    --loglevel=info   # agent job (LLM)
  celery -A agent_worker.celery_app worker -Q dispatch --loglevel=info   # gửi đa kênh

Polling: dùng AsyncResult(task_id).state + .info/.result (metadata bơm qua update_state).
RabbitMQ = broker (ack/retry/DLQ chắc chắn cho task LLM chạy lâu); Redis = nơi lưu
trạng thái + kết quả để BackEnd Services polling.
"""

from __future__ import annotations

from celery import Celery

from agent_worker.config import get_worker_settings

_s = get_worker_settings()

app = Celery(
    "quto_agent",
    broker=_s.rabbitmq_url,
    backend=_s.redis_url,
    include=["agent_worker.tasks"],
)

app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    task_track_started=True,           # có state STARTED để polling thấy "đang chạy"
    result_extended=True,
    result_expires=24 * 3600,
    task_default_queue="agent",
    task_routes={
        "agent.run_job": {"queue": "agent"},
        "agent.resume_job": {"queue": "agent"},
        "agent.dispatch_message": {"queue": "dispatch"},
    },
    worker_prefetch_multiplier=1,
)
