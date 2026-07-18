"""Graph = agent ReAct (LangGraph tool-calling). Xem ai/chat_model.py + graph/agent_tools.py.

Agent tự điều phối tool (get_forecast → assess_risk → … → compose_bulletins). Dispatch KHÔNG
nằm trong graph: agent chỉ soạn bản tin, tầng task (tasks.py) quyết định gửi sau khi cán bộ duyệt.
"""

from __future__ import annotations

from agent_worker.ai.chat_model import build_agent


def get_graph():
    """Trả agent ReAct đã compile (cache singleton nằm trong build_agent)."""
    return build_agent()
