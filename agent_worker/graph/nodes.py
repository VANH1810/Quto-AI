"""Các node LangGraph. Mỗi node = 1 span 'node'; tool/llm gọi bên trong = span con.

Span tự ghi vào LLM DB qua context manager `span()` (parent lấy từ contextvar). Nhờ
vậy node code gọn mà vẫn có đủ vết tool call / response / thinking theo dòng thời gian.
"""

from __future__ import annotations

import time
import uuid
from contextlib import asynccontextmanager
from contextvars import ContextVar

from agent_worker.config import get_worker_settings as backend_settings
from agent_worker.shared.alert import HazardEvent
from agent_worker.shared.common import Lang

from agent_worker.config import get_worker_settings
from agent_worker import repo
from agent_worker.tools import (geo_tool, recommend_tool, risk_engine_tool,
                                shelter_tool, user_api_tool, weather_tool,
                                zalo_formatter)

_node_span: ContextVar[str | None] = ContextVar("_node_span", default=None)
# Hook báo tiến độ (Celery update_state) — tasks.py set trước khi chạy graph.
progress_hook: ContextVar["callable | None"] = ContextVar("progress_hook", default=None)


@asynccontextmanager
async def span(run_id: str, kind: str, name: str, *, input: dict | None = None):
    """Mở/đóng 1 span; kind='node' tự làm parent cho tool/llm trong nó (contextvar)."""
    parent = None if kind == "node" else _node_span.get()
    if kind == "node":
        hook = progress_hook.get()
        if hook is not None:
            try:
                hook(name)                 # báo Celery: đang ở node nào
            except Exception:              # noqa: BLE001 — không để progress làm gãy graph
                pass
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


# --------------------------------------------------------------------------- nodes

async def ingest(state: dict) -> dict:
    run_id, code = state["run_id"], state["commune_code"]
    async with span(run_id, "node", "ingest"):
        commune = state.get("commune") or geo_tool.get_commune(code)
        if commune is None:
            raise ValueError(f"Không tìm thấy xã: {code}")
        forecast = state.get("forecast")
        if not forecast:
            async with span(run_id, "tool", "weather", input={"commune_code": code}) as sp:
                forecast = await weather_tool.get_forecast(commune, days=7)
                sp["output"] = {"source": forecast.get("source"), "days": len(forecast.get("days", []))}
        return {"commune": commune, "forecast": forecast}


async def assess_risk(state: dict) -> dict:
    run_id = state["run_id"]
    async with span(run_id, "node", "assess_risk"):
        async with span(run_id, "tool", "risk_engine",
                        input={"commune_code": state["commune_code"]}) as sp:
            events = risk_engine_tool.evaluate(state["forecast"], state["commune"])
            top = risk_engine_tool.top_event(events)
            sp["output"] = {"n_events": len(events),
                            "top": {"hazard": top["hazard"], "risk_level": top["risk_level"]} if top else None}
        out: dict = {"hazard_events": events, "top_event": top}
        if top:
            out["risk_level"] = top["risk_level"]
            out["alert_id"] = "alt_" + uuid.uuid4().hex[:10]
        else:
            out["status"] = "no_risk"
        return out


def has_risk(state: dict) -> str:
    return "yes" if state.get("top_event") else "no"


async def lookup_actions(state: dict) -> dict:
    run_id, top = state["run_id"], state["top_event"]
    async with span(run_id, "node", "lookup_actions"):
        async with span(run_id, "tool", "recommend",
                        input={"hazard": top["hazard"], "level": top["risk_level"]}) as sp:
            actions = recommend_tool.lookup(top["hazard"], top["risk_level"], state["commune"])
            sp["output"] = {"actions": actions}
        return {"actions": actions}


async def enrich_recipients(state: dict) -> dict:
    run_id, code = state["run_id"], state["commune_code"]
    async with span(run_id, "node", "enrich_recipients"):
        async with span(run_id, "tool", "user_api", input={"commune_code": code}) as sp:
            citizens = await user_api_tool.citizens_by_commune(code)
            admins = await user_api_tool.admins_for_commune(code)
            sp["output"] = {"n_citizens": len(citizens), "n_admins": len(admins)}
        async with span(run_id, "tool", "shelter", input={"commune_code": code}) as sp:
            shelters = await shelter_tool.nearest_for_commune(code, citizens)
            sp["output"] = {"n_shelters_matched": len(shelters)}
        return {"recipients": {"citizens": citizens, "admins": admins, "shelters": shelters}}


async def compose(state: dict) -> dict:
    run_id, top = state["run_id"], dict(state["top_event"])
    top["recommended_actions"] = state.get("actions", top.get("recommended_actions", []))
    lang_enums = [Lang(l) for l in state.get("langs", ["vi"])]
    from agent_worker.ai import llm

    async with span(run_id, "node", "compose"):
        async with span(run_id, "llm", backend_settings().llm_provider,
                        input={"event": top, "langs": [l.value for l in lang_enums]}) as sp:
            bulletins_objs, meta = await _generate_with_meta(llm, top, lang_enums)
            bulletins = [b.model_dump() if hasattr(b, "model_dump") else b for b in bulletins_objs]
            vi = next((b for b in bulletins if b["lang"] == "vi"), bulletins[0] if bulletins else {})
            sp["content"] = vi.get("body", "")
            sp["thinking"] = meta.get("thinking")
            sp["tokens"] = meta.get("usage")
            sp["output"] = {"bulletins": bulletins}

        payloads = zalo_formatter.build(top, bulletins, state["recipients"], state.get("actions", []))
        await repo.update_alert_bulletins(state.get("alert_id"), bulletins)
        return {"bulletins": bulletins, "zalo_payloads": payloads}


async def _generate_with_meta(llm, top: dict, lang_enums: list[Lang]):
    """Gọi llm.generate_bulletins; nếu llm có bản trả kèm meta thì dùng, không thì rỗng."""
    event = HazardEvent(**top)
    if hasattr(llm, "generate_bulletins_with_meta"):
        return await llm.generate_bulletins_with_meta(event, lang_enums)
    bulletins = await llm.generate_bulletins(event, lang_enums)
    return bulletins, {"thinking": None, "usage": {}}


async def human_gate(state: dict) -> dict:
    run_id = state["run_id"]
    threshold = get_worker_settings().human_approval_min_level
    needs = int(state.get("risk_level", 0)) >= threshold
    async with span(run_id, "node", "human_gate") as sp:
        sp["output"] = {"risk_level": state.get("risk_level"), "threshold": threshold, "needs_human": needs}
    # Không tự gửi ở đây: tầng task (tasks.py) quyết định dispatch ngay (cấp thấp)
    # hay chờ cán bộ duyệt (cấp >= ngưỡng).
    return {"needs_human": needs, "status": "pending_approval" if needs else "approved"}
