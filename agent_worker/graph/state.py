"""State của LangGraph — truyền qua các node (partial update mỗi node)."""

from __future__ import annotations

from typing import TypedDict


class AgentState(TypedDict, total=False):
    # định danh
    job_id: str
    run_id: str                 # = job_id (tương quan trace)
    alert_id: str | None

    # đầu vào
    commune_code: str
    langs: list[str]            # ['vi','tai','hmn']
    trigger: str

    # dữ liệu qua các node
    forecast: dict | None
    commune: dict | None
    hazard_events: list[dict]
    top_event: dict | None
    risk_level: int
    actions: list[str]
    recipients: dict            # {citizens:[...], admins:[...], shelters:{cccd: shelter}}
    bulletins: list[dict]       # kết quả LLM (đa ngữ)
    zalo_payloads: list[dict]   # message đã format / người nhận

    # điều khiển
    needs_human: bool
    status: str
