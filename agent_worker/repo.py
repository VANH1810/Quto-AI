"""Ghi LLM Result DB (agent_runs + agent_spans) + cập nhật bản tin (best-effort).

Quy ước: run_id = job_id (tương quan trực tiếp job ↔ trace). span_id = spn_xxx.
seq tự tăng theo run (đếm in-memory) để node khỏi phải tự quản thứ tự.
"""

from __future__ import annotations

import logging
import uuid
from collections import defaultdict

from sqlalchemy import update

from agent_worker.infra.db import AgentRun, AgentSpan, session
from sqlalchemy.sql import func

log = logging.getLogger("agent_worker.repo")

_seq: dict[str, int] = defaultdict(int)


def _next_seq(run_id: str) -> int:
    _seq[run_id] += 1
    return _seq[run_id]


async def save_run(run_id: str, *, commune_code: str, trigger: str,
                   langs: list[str], llm_provider: str, status: str = "running") -> str:
    async with session() as s:
        s.add(AgentRun(id=run_id, commune_code=commune_code, trigger=trigger,
                       langs=langs, llm_provider=llm_provider, status=status))
    return run_id


async def update_run_status(run_id: str, status: str, *, risk_level: int | None = None,
                            alert_id: str | None = None, tokens: dict | None = None,
                            error: str | None = None, finished: bool = False) -> None:
    values: dict = {"status": status, "updated_at": func.now()}
    if risk_level is not None:
        values["risk_level"] = risk_level
    if alert_id is not None:
        values["alert_id"] = alert_id
    if error is not None:
        values["error"] = error
    if tokens:
        values["prompt_tokens"] = tokens.get("prompt_tokens", 0)
        values["completion_tokens"] = tokens.get("completion_tokens", 0)
        values["total_tokens"] = tokens.get("total_tokens", 0)
    if finished:
        values["finished_at"] = func.now()
    async with session() as s:
        await s.execute(update(AgentRun).where(AgentRun.id == run_id).values(**values))


async def open_span(run_id: str, kind: str, name: str, *,
                    parent_span_id: str | None = None, input: dict | None = None) -> str:
    span_id = "spn_" + uuid.uuid4().hex[:12]
    async with session() as s:
        s.add(AgentSpan(id=span_id, run_id=run_id, parent_span_id=parent_span_id,
                        seq=_next_seq(run_id), kind=kind, name=name,
                        status="running", input=input))
    return span_id


async def close_span(span_id: str, *, status: str = "ok", output: dict | None = None,
                     content: str | None = None, thinking: str | None = None,
                     tokens: dict | None = None, latency_ms: int | None = None,
                     error: str | None = None) -> None:
    values: dict = {"status": status}
    if output is not None:
        values["output"] = output
    if content is not None:
        values["content"] = content
    if thinking is not None:
        values["thinking"] = thinking
    if latency_ms is not None:
        values["latency_ms"] = latency_ms
    if error is not None:
        values["error"] = error
    if tokens:
        values["prompt_tokens"] = tokens.get("prompt_tokens")
        values["completion_tokens"] = tokens.get("completion_tokens")
        values["total_tokens"] = tokens.get("total_tokens")
    async with session() as s:
        await s.execute(update(AgentSpan).where(AgentSpan.id == span_id).values(**values))


async def update_alert_bulletins(alert_id: str | None, bulletins: list[dict]) -> None:
    """Cập nhật alerts.bulletins nếu bảng/hàng tồn tại (best-effort, không chặn luồng).

    Backend mặc định chạy in-memory (process khác) nên đây chỉ có tác dụng khi
    nghiệp vụ cũng được đẩy vào cùng Postgres. Bulletins luôn có trong span.output +
    Redis result nên không mất mát dữ liệu.
    """
    if not alert_id:
        return
    import json

    from sqlalchemy import text
    try:
        async with session() as s:
            await s.execute(
                text("UPDATE public.alerts SET bulletins = :b WHERE id = :id"),
                {"b": json.dumps(bulletins, ensure_ascii=False), "id": alert_id},
            )
    except Exception as e:  # noqa: BLE001
        log.debug("Bỏ qua cập nhật alerts.bulletins: %s", e)
