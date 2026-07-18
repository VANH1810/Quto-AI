"""Agent ReAct (LangGraph) — gọi LLM TRỰC TIẾP bằng thư viện `openai` (không LangChain).

Graph 2 node: `agent` (gọi openai chat.completions kèm tools → nếu có tool_calls thì đi tiếp)
⇄ `tools` (thực thi tool trong agent_tools rồi trả kết quả về hội thoại). Lặp tới khi model
không gọi tool nữa. Config chỉ đóng vai trò: provider + api key (+ model/base_url).
"""

from __future__ import annotations

import logging

from langgraph.graph import END, StateGraph
from typing_extensions import TypedDict

from agent_worker.config import openai_client_params
from agent_worker.graph import agent_tools

log = logging.getLogger("agent_worker.agent")

SYSTEM_PROMPT = (
    "Bạn là AGENT cảnh báo thiên tai cấp xã của tỉnh Điện Biên. Nhiệm vụ: quét nguy cơ và "
    "SOẠN bản tin cảnh báo — KHÔNG tự gửi cho ai.\n\n"
    "Quy trình BẮT BUỘC, gọi tool theo đúng thứ tự:\n"
    "1) get_forecast — lấy dự báo thời tiết của xã.\n"
    "2) assess_risk — đánh giá nguy cơ theo QĐ18. Đây là NGUỒN DUY NHẤT quyết định có/không "
    "nguy cơ và cấp độ; bạn KHÔNG được tự suy diễn cấp độ.\n"
    "   • Nếu assess_risk báo KHÔNG có nguy cơ (no_risk) → DỪNG NGAY, trả lời ngắn gọn, "
    "KHÔNG gọi tool nào nữa.\n"
    "   • Nếu CÓ nguy cơ → tiếp tục:\n"
    "3) recommend_actions — tra khuyến nghị hành động.\n"
    "4) get_recipients — lấy dân + cán bộ + nơi trú ẩn.\n"
    "5) compose_bulletins — soạn bản tin đa ngữ. Sau bước này thì HOÀN TẤT, dừng lại.\n\n"
    "TUYỆT ĐỐI KHÔNG bịa số liệu, không đổi cấp độ rủi ro, không gọi tool gửi (không tồn tại). "
    "Mỗi tool chỉ cần gọi một lần. Khi xong, trả lời một câu tóm tắt."
)

_agent = None


class _AgentState(TypedDict):
    messages: list


def _client_and_model():
    """(AsyncOpenAI, model) cho provider hiện tại (openai/local/fpt) — endpoint OpenAI-compatible."""
    p = openai_client_params()
    from openai import AsyncOpenAI
    return AsyncOpenAI(api_key=p["api_key"], base_url=p["base_url"]), p["model"]


async def _agent_node(state: _AgentState) -> dict:
    """Gọi LLM (kèm danh sách tools). Trả assistant message (có thể chứa tool_calls)."""
    client, model = _client_and_model()
    resp = await client.chat.completions.create(
        model=model,
        messages=[{"role": "system", "content": SYSTEM_PROMPT}, *state["messages"]],
        tools=agent_tools.TOOL_SCHEMAS,
        tool_choice="auto",
        temperature=0,
    )
    msg = resp.choices[0].message
    calls = [tc.function.name for tc in (msg.tool_calls or [])]
    if calls:
        log.info("🧠 agent quyết định gọi tool: %s", ", ".join(calls))
    else:
        log.info("🧠 agent kết thúc: %s", (getattr(msg, "content", None) or "").strip()[:200])
    return {"messages": [*state["messages"], msg.model_dump(exclude_none=True)]}


async def _tools_node(state: _AgentState) -> dict:
    """Thực thi các tool_calls của lượt assistant vừa rồi → nối ToolMessage vào hội thoại."""
    last = state["messages"][-1]
    out = list(state["messages"])
    for tc in last.get("tool_calls", []):
        name = tc["function"]["name"]
        fn = agent_tools.TOOL_FUNCS.get(name)
        if fn is None:
            result = f"Lỗi: tool '{name}' không tồn tại."
        else:
            try:
                result = await fn()
            except Exception as e:  # noqa: BLE001 — trả lỗi cho model biết, không sập graph
                result = f"Lỗi khi chạy {name}: {e}"
        log.info("🔧 %s → %s", name, str(result)[:200])
        out.append({"role": "tool", "tool_call_id": tc["id"], "content": str(result)})
    return {"messages": out}


def _route(state: _AgentState) -> str:
    """Còn tool_calls → chạy tools; hết → kết thúc."""
    return "tools" if state["messages"][-1].get("tool_calls") else "end"


def build_agent():
    """Compile graph ReAct (cache singleton)."""
    global _agent
    if _agent is not None:
        return _agent
    g = StateGraph(_AgentState)
    g.add_node("agent", _agent_node)
    g.add_node("tools", _tools_node)
    g.set_entry_point("agent")
    g.add_conditional_edges("agent", _route, {"tools": "tools", "end": END})
    g.add_edge("tools", "agent")
    _agent = g.compile()
    return _agent


__all__ = ["build_agent", "SYSTEM_PROMPT"]
