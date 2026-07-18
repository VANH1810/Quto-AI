"""Hạ tầng đo đạc cho agent: span (trace vào LLM DB) + progress (polling Celery).

Trước đây file này chứa các node của DAG tất định. Sau khi chuyển sang agent ReAct
(tool-calling), logic nghiệp vụ nằm ở graph/agent_tools.py; ở đây chỉ còn primitive
dùng chung: `span()` mở/đóng span, `_record()`/`_emit()` đẩy tiến độ + kết quả tích luỹ.
"""

from __future__ import annotations

import time
from contextlib import asynccontextmanager
from contextvars import ContextVar

from agent_worker import repo

_node_span: ContextVar[str | None] = ContextVar("_node_span", default=None)
# Hook báo tiến độ (callable(meta: dict) → Celery update_state) — tasks.py set trước khi chạy.
progress_hook: ContextVar["callable | None"] = ContextVar("progress_hook", default=None)
# Accumulator kết quả tích luỹ theo từng bước (risk_level → bulletins → ...), lộ ra khi polling.
progress_state: ContextVar[dict | None] = ContextVar("progress_state", default=None)

# Thứ tự tool để suy step/total cho polling (agent có thể gọi lệch, chỉ mang tính hiển thị).
_STEP = {"get_forecast": 1, "assess_risk": 2, "recommend_actions": 3,
         "get_recipients": 4, "compose_bulletins": 5}


def _record(**fields) -> None:
    """Ghi kết quả từng phần vào accumulator (để progress mang theo result đang sinh)."""
    acc = progress_state.get()
    if acc is not None:
        acc.update(fields)


def _emit(node: str) -> None:
    """Báo tiến độ + result tích luỹ tới nay cho Celery (polling đọc được)."""
    cb = progress_hook.get()
    if cb is None:
        return
    acc = progress_state.get() or {}
    try:
        cb({"node": node, "step": _STEP.get(node, 0), "total": len(_STEP), "result": dict(acc)})
    except Exception:  # noqa: BLE001 — progress không được làm gãy agent
        pass


@asynccontextmanager
async def span(run_id: str, kind: str, name: str, *, input: dict | None = None):
    """Mở/đóng 1 span; kind='node' tự làm parent cho tool/llm trong nó (contextvar)."""
    parent = None if kind == "node" else _node_span.get()
    if kind == "node":
        _emit(name)
    span_id = await repo.open_span(run_id, kind, name, parent_span_id=parent, input=input)
    token = _node_span.set(span_id) if kind == "node" else None
    started = time.monotonic()
    holder: dict = {}
    try:
        yield holder
        await repo.close_span(
            span_id, status="ok",
            output=holder.get("output"), content=holder.get("content"),
            thinking=holder.get("thinking"), tokens=holder.get("tokens"),
            latency_ms=int((time.monotonic() - started) * 1000),
        )
    except Exception as e:  # noqa: BLE001
        await repo.close_span(span_id, status="error", error=str(e),
                              latency_ms=int((time.monotonic() - started) * 1000))
        raise
    finally:
        if token is not None:
            _node_span.reset(token)
