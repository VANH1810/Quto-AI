"""Contracts truyền qua RabbitMQ giữa BackEnd Services ↔ agent_worker ↔ dispatch_worker."""

from __future__ import annotations

import uuid
from typing import Literal

from pydantic import BaseModel, Field

_DEFAULT_LANGS = ["vi", "tai", "hmn"]


def new_job_id() -> str:
    return "job_" + uuid.uuid4().hex[:12]


class AgentJobRequest(BaseModel):
    """BackEnd Services → agent.jobs.q : yêu cầu quét + sinh cảnh báo cho 1 xã."""

    job_id: str = Field(default_factory=new_job_id)
    commune_code: str
    langs: list[str] = Field(default_factory=lambda: list(_DEFAULT_LANGS))
    forecast: dict | None = None          # nếu BackEnd đã kèm forecast thì graph khỏi gọi lại
    trigger: str = "manual"               # manual | scheduler | threshold
    requested_by: str | None = None


class AgentControlCommand(BaseModel):
    """Backend (khi admin duyệt) → agent.control.q : resume/reject 1 job đang chờ."""

    job_id: str
    action: Literal["approve", "reject"]
    admin_id: str
    edited_body_vi: str | None = None     # admin sửa nội dung tiếng Việt trước khi gửi
    note: str | None = None


class DispatchMessage(BaseModel):
    """graph.dispatch → dispatch.{channel}.q : gửi 1 bản tin tới 1 người nhận."""

    job_id: str
    alert_id: str | None = None
    channel: str                          # zalo_zns | sms | loudspeaker
    commune_code: str
    commune_name: str = ""
    recipient: dict                       # {cccd, full_name, phone, address, lat, lon}
    lang: str = "vi"
    title: str = ""
    body: str = ""
    zalo_template: dict | None = None     # data cho Zalo ZNS template
    nearest_shelter: dict | None = None   # {id, name, address, km}
    attempt: int = 0
