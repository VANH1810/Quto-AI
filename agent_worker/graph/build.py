"""Dựng StateGraph LangGraph: ingest → assess_risk → … → compose → human_gate → END.

Với Celery, dispatch KHÔNG nằm trong graph (worker đa tiến trình không share checkpoint):
graph chỉ lo phần suy luận + sinh bản tin (LLM), kết thúc sau human_gate với
`needs_human` + `zalo_payloads`. Tầng task (tasks.py) quyết định gửi ngay hay chờ duyệt.
"""

from __future__ import annotations

from langgraph.graph import END, StateGraph

from agent_worker.graph import nodes
from agent_worker.graph.state import AgentState

_graph = None


def build_graph():
    g = StateGraph(AgentState)
    g.add_node("ingest", nodes.ingest)
    g.add_node("assess_risk", nodes.assess_risk)
    g.add_node("lookup_actions", nodes.lookup_actions)
    g.add_node("enrich_recipients", nodes.enrich_recipients)
    g.add_node("compose", nodes.compose)
    g.add_node("human_gate", nodes.human_gate)

    g.set_entry_point("ingest")
    g.add_edge("ingest", "assess_risk")
    g.add_conditional_edges("assess_risk", nodes.has_risk,
                            {"yes": "lookup_actions", "no": END})
    g.add_edge("lookup_actions", "enrich_recipients")
    g.add_edge("enrich_recipients", "compose")
    g.add_edge("compose", "human_gate")
    g.add_edge("human_gate", END)
    return g.compile()


def get_graph():
    global _graph
    if _graph is None:
        _graph = build_graph()
    return _graph
