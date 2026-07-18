"""Tool cho agent ReAct — MỖI tool bọc đúng hàm nghiệp vụ cũ (logic KHÔNG đổi).

Hàm thuần async (KHÔNG dùng LangChain): vòng tool-calling do chat_model.py gọi openai SDK
điều phối. `TOOL_FUNCS` (name→coroutine) để dispatch, `TOOL_SCHEMAS` (định dạng tools của
OpenAI) để gửi cho model. Tất cả tool KHÔNG nhận tham số (dữ liệu ở run_ctx).

Dữ liệu lớn (forecast/recipients/bulletins) KHÔNG đi qua token LLM: tool đọc/ghi vào
`run_ctx` (contextvar, đặt bởi runner mỗi job), chỉ TRẢ tóm tắt ngắn để LLM suy luận bước kế.
Progress/span dùng lại hạ tầng ở nodes.py (span/_record/_emit) → polling & trace không đổi.
"""

from __future__ import annotations

import uuid
from contextvars import ContextVar

from agent_worker import repo
from agent_worker.graph import nodes
from agent_worker.shared.alert import HazardEvent
from agent_worker.shared.common import Lang
from agent_worker.tools import (geo_tool, maps_tool, message_formatter,
                                risk_engine_tool, shelter_tool, user_api_tool,
                                weather_tool)

# Ngữ cảnh 1 job (per-thread/per-task): runner set trước khi chạy agent, tool đọc/ghi.
run_ctx: ContextVar[dict | None] = ContextVar("run_ctx", default=None)


def _ctx() -> dict:
    c = run_ctx.get()
    if c is None:
        raise RuntimeError("run_ctx chưa được khởi tạo (runner.run_graph phải set trước).")
    return c


async def get_forecast() -> str:
    """Lấy thông tin xã + dự báo thời tiết nhiều ngày cho xã đang xử lý. Gọi ĐẦU TIÊN."""
    ctx = _ctx()
    code, run_id = ctx["commune_code"], ctx["run_id"]
    async with nodes.span(run_id, "node", "get_forecast"):
        commune = ctx.get("commune") or geo_tool.get_commune(code)
        if commune is None:
            raise ValueError(f"Không tìm thấy xã: {code}")
        forecast = ctx.get("forecast")
        if not forecast:
            async with nodes.span(run_id, "tool", "weather", input={"commune_code": code}) as sp:
                forecast = await weather_tool.get_forecast(commune, days=7)
                sp["output"] = {"source": forecast.get("source"), "days": len(forecast.get("days", []))}
        ctx["commune"], ctx["forecast"] = commune, forecast
    nodes._emit("get_forecast")
    return (f"Đã lấy dự báo cho xã {commune.get('name', code)}: nguồn "
            f"{forecast.get('source')}, {len(forecast.get('days', []))} ngày.")


async def assess_risk() -> str:
    """Đánh giá nguy cơ theo quy tắc QĐ18 (nguồn DUY NHẤT quyết định cấp độ). Gọi sau get_forecast.

    Nếu KHÔNG có nguy cơ → DỪNG quy trình, không cần gọi tool nào nữa.
    """
    ctx = _ctx()
    run_id = ctx["run_id"]
    async with nodes.span(run_id, "node", "assess_risk"):
        async with nodes.span(run_id, "tool", "risk_engine",
                              input={"commune_code": ctx["commune_code"]}) as sp:
            events = risk_engine_tool.evaluate(ctx["forecast"], ctx["commune"])
            top = risk_engine_tool.top_event(events)
            sp["output"] = {"n_events": len(events),
                            "top": {"hazard": top["hazard"], "risk_level": top["risk_level"]} if top else None}
        ctx["hazard_events"] = events
        ctx["top_event"] = top
        if top:
            ctx["risk_level"] = top["risk_level"]
            ctx["alert_id"] = "alt_" + uuid.uuid4().hex[:10]
            nodes._record(risk_level=top["risk_level"], hazard=top["hazard"],
                          risk_label=top.get("risk_label"), top_event=top)
        else:
            ctx["risk_level"] = 0
            ctx["status"] = "no_risk"
            nodes._record(status="no_risk", risk_level=0)
    nodes._emit("assess_risk")
    if not top:
        return "KHÔNG có nguy cơ (no_risk). DỪNG — không soạn/gửi cảnh báo."
    return (f"Có nguy cơ: {top['hazard']} cấp {top['risk_level']} "
            f"({top.get('risk_label', '')}). alert_id={ctx['alert_id']}. Tiếp tục recommend_actions.")


async def recommend_actions() -> str:
    """Tra khuyến nghị hành động cho nguy cơ hiện tại. Gọi sau assess_risk (khi CÓ nguy cơ)."""
    ctx = _ctx()
    run_id, top = ctx["run_id"], ctx.get("top_event")
    if not top:
        return "Chưa có nguy cơ — không cần khuyến nghị."
    from agent_worker.ai import llm
    async with nodes.span(run_id, "node", "recommend_actions"):
        async with nodes.span(run_id, "tool", "recommend",
                              input={"hazard": top["hazard"], "level": top["risk_level"]}) as sp:
            # LLM đề xuất theo tình huống (KB fallback bên trong generate_actions)
            actions = await llm.generate_actions(HazardEvent(**top), ctx.get("commune") or {},
                                                 ctx.get("forecast") or {})
            sp["output"] = {"actions": actions}
        ctx["actions"] = actions
        nodes._record(actions=actions)
    nodes._emit("recommend_actions")
    return "Khuyến nghị hành động: " + "; ".join(actions)


async def get_recipients() -> str:
    """Lấy danh sách dân + cán bộ của xã và nơi trú ẩn gần nhất mỗi người. Gọi trước compose."""
    ctx = _ctx()
    run_id, code = ctx["run_id"], ctx["commune_code"]
    async with nodes.span(run_id, "node", "get_recipients"):
        import asyncio
        async with nodes.span(run_id, "tool", "user_api", input={"commune_code": code}) as sp:
            citizens, admins = await asyncio.gather(
                user_api_tool.citizens_by_commune(code),
                user_api_tool.admins_for_commune(code))
            sp["output"] = {"n_citizens": len(citizens), "n_admins": len(admins)}
        async with nodes.span(run_id, "tool", "shelter", input={"commune_code": code}) as sp:
            shelters = await shelter_tool.nearest_for_commune(code, citizens)
            n_poi, n_route = await _enrich_shelters(citizens, shelters)
            sp["output"] = {"n_shelters_matched": len(shelters), "poi_fallback": n_poi, "routes": n_route}
        ctx["recipients"] = {"citizens": citizens, "admins": admins, "shelters": shelters}
        nodes._record(n_recipients=len(citizens), n_admins=len(admins))
    nodes._emit("get_recipients")
    return f"Có {len(citizens)} người dân và {len(admins)} cán bộ. Tiếp tục compose_bulletins."


async def _enrich_shelters(citizens: list[dict], shelters: dict) -> tuple[int, int]:
    """Xã thiếu shelter DB → POI SerpApi (flag); người nhận Telegram → km/phút đường thật.

    Best-effort: SerpApi không bật/lỗi → giữ nguyên (haversine / bỏ dòng). POI cache theo vùng
    nên nhiều dân cùng xã chỉ gọi ~1 lần; travel chỉ cho người có telegram_chat_id (giới hạn chi phí).
    """
    n_poi = n_route = 0
    for c in citizens:
        cccd, clat, clon = c.get("cccd"), c.get("lat"), c.get("lon")
        sh = shelters.get(cccd)
        if sh is None:                                  # chưa có shelter DB → POI tạm
            poi = await maps_tool.nearby_shelters(clat, clon)
            if poi:
                shelters[cccd] = sh = poi
                n_poi += 1
        if sh and c.get("telegram_chat_id") and clat is not None and sh.get("lat") is not None:
            route = await maps_tool.travel((clat, clon), (sh["lat"], sh["lon"]))
            if route:
                sh["distance_text"] = route.get("distance_text")
                sh["duration_text"] = route.get("duration_text")
                if route.get("distance_km") is not None:
                    sh["distance_km"] = route["distance_km"]
                sh["duration_min"] = route.get("duration_min")
                n_route += 1
    return n_poi, n_route


async def compose_bulletins() -> str:
    """Soạn bản tin cảnh báo đa ngữ (vi/tai/hmn) cho nguy cơ hiện tại. Gọi CUỐI CÙNG.

    KHÔNG gửi tin — việc gửi do hệ thống quyết định sau khi cán bộ duyệt.
    """
    ctx = _ctx()
    run_id = ctx["run_id"]
    top = dict(ctx.get("top_event") or {})
    if not top:
        return "Chưa có nguy cơ — không soạn bản tin."
    top["recommended_actions"] = ctx.get("actions", top.get("recommended_actions", []))
    lang_enums = [Lang(l) for l in ctx.get("langs", ["vi"])]
    from agent_worker.ai import llm

    async with nodes.span(run_id, "node", "compose_bulletins"):
        async with nodes.span(run_id, "llm", "compose",
                              input={"event": top, "langs": [l.value for l in lang_enums]}) as sp:
            event = HazardEvent(**top)
            bulletins_objs, meta = await llm.generate_bulletins_with_meta(event, lang_enums)
            bulletins = [b.model_dump() if hasattr(b, "model_dump") else b for b in bulletins_objs]
            vi = next((b for b in bulletins if b["lang"] == "vi"), bulletins[0] if bulletins else {})
            sp["content"] = vi.get("body", "")
            sp["thinking"] = meta.get("thinking")
            sp["tokens"] = meta.get("usage")
            sp["output"] = {"bulletins": bulletins}
        payloads = message_formatter.build(top, bulletins, ctx.get("recipients", {}), ctx.get("actions", []))
        await repo.update_alert_bulletins(ctx.get("alert_id"), bulletins)
        ctx["bulletins"] = bulletins
        ctx["payloads"] = payloads
        nodes._record(bulletins=bulletins, actions=ctx.get("actions", []))
    nodes._emit("compose_bulletins")
    return (f"Đã soạn xong bản tin {len(bulletins)} ngôn ngữ. "
            f"Tiêu đề (vi): {vi.get('title', '')}. Hoàn tất — dừng lại.")


# Registry name→coroutine (dispatch khi model gọi tool) + tóm tắt để dựng schema.
_TOOLS = [
    (get_forecast, "Lấy thông tin xã + dự báo thời tiết. Gọi ĐẦU TIÊN."),
    (assess_risk, "Đánh giá nguy cơ theo QĐ18 (nguồn DUY NHẤT quyết định cấp độ). "
                  "Nếu no_risk thì DỪNG."),
    (recommend_actions, "Tra khuyến nghị hành động (khi có nguy cơ)."),
    (get_recipients, "Lấy dân + cán bộ + nơi trú ẩn của xã."),
    (compose_bulletins, "Soạn bản tin đa ngữ. Gọi CUỐI CÙNG. Không gửi tin."),
]

TOOL_FUNCS = {fn.__name__: fn for fn, _ in _TOOLS}

# Định dạng 'tools' của OpenAI Chat Completions. Tool không nhận tham số → parameters rỗng.
TOOL_SCHEMAS = [
    {"type": "function",
     "function": {"name": fn.__name__, "description": desc,
                  "parameters": {"type": "object", "properties": {}, "required": []}}}
    for fn, desc in _TOOLS
]
