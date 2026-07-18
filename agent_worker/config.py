"""Cấu hình worker — đọc từ .env (pydantic-settings). Hạ tầng bắt buộc (Docker)."""

from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class WorkerSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Hạ tầng
    #   Broker Celery: mặc định DÙNG REDIS (1 hạ tầng cho cả broker + result → free-host dễ,
    #   ít RAM, ổn định hơn). Muốn RabbitMQ thì set CELERY_BROKER_URL=amqp://...
    rabbitmq_url: str = "amqp://guest:guest@rabbitmq:5672/"
    redis_url: str = "redis://redis:6379/0"
    celery_broker_url: str = ""   # rỗng → dùng redis_url làm broker
    database_url: str = "postgresql+asyncpg://quto:quto@postgres:5432/quto"

    # LLM (mock | openai | local | fpt | gemini)
    llm_provider: str = "mock"
    openai_api_key: str = ""
    openai_base_url: str = "https://api.openai.com/v1"
    openai_model: str = "gpt-4o-mini"
    gemini_api_key: str = ""
    gemini_model: str = "gemini-1.5-flash"
    # FPT Cloud (OpenAI-compatible) — dùng openai SDK, chỉ khác base_url/model/key.
    fpt_api_key: str = ""
    fpt_base_url: str = "https://mkp-api.fptcloud.com/v1/"
    fpt_model: str = "DeepSeek-V4-Flash"

    # Tai Dam (Thái Đen): cho phép dùng câu NHÁP chưa duyệt (demo). Production=False → chỉ
    # phát câu đã verify hoặc fallback tiếng Việt (không phát Tai Dam chưa duyệt).
    tai_dam_allow_draft: bool = True

    # TTS (mock | mms) — dùng bởi shared/tts.py
    tts_provider: str = "mock"

    # Thời tiết (openmeteo | mock) — dùng bởi shared/weather.py
    weather_provider: str = "openmeteo"
    openmeteo_base_url: str = "https://api.open-meteo.com/v1/forecast"
    # WEATHER_PROVIDER=mock: sinh kịch bản MƯA LỚN để demo (đỉnh mm/24h). Chỉ dùng khi mock,
    # KHÔNG áp cho fallback lỗi mạng (fallback giữ 'hiền' để tránh cảnh báo giả).
    mock_precip_mm: float = 220.0

    # Bản đồ/định tuyến (none | serpapi) — km/phút đường thật + tìm POI trú ẩn qua SerpApi.
    route_provider: str = "none"
    serpapi_key: str = ""
    serpapi_base_url: str = "https://serpapi.com/search"

    # Human-in-the-loop: cấp >= ngưỡng phải chờ cán bộ duyệt (1..5). 3 = cam.
    human_approval_min_level: int = 3

    # Callback về backend (ghi notifications). service_token phải TRÙNG backend.
    backend_url: str = "http://host.docker.internal:8000"
    service_token: str = "doi-chuoi-bi-mat-nay"

    # Telegram: mock | live. Gửi cảnh báo qua Telegram Bot API.
    telegram_provider: str = "mock"
    telegram_bot_token: str = ""      # từ @BotFather

    # Tuning
    prefetch: int = 8
    dispatch_max_retry: int = 3

    @property
    def broker_url(self) -> str:
        """Broker Celery hiệu dụng: CELERY_BROKER_URL nếu đặt, ngược lại dùng Redis."""
        return self.celery_broker_url or self.redis_url


@lru_cache
def get_worker_settings() -> WorkerSettings:
    return WorkerSettings()


# Provider dùng chung 1 client OpenAI-compatible (openai SDK): openai | local | fpt.
_OPENAI_COMPATIBLE = {"openai", "local", "fpt"}


def openai_client_params() -> dict:
    """Trả {api_key, base_url, model} cho provider hiện tại (openai/local/fpt).

    Dùng chung cho agent (chat_model) và soạn bản tin (ai/llm). Raise nếu provider không
    phải loại OpenAI-compatible hoặc thiếu credential.
    """
    s = get_worker_settings()
    p = s.llm_provider.lower()
    if p not in _OPENAI_COMPATIBLE:
        raise RuntimeError(
            f"LLM_PROVIDER='{p}' không phải loại OpenAI-compatible (cần: openai | local | fpt).")
    if p == "fpt":
        if not s.fpt_api_key:
            raise RuntimeError("Thiếu FPT_API_KEY cho LLM_PROVIDER=fpt.")
        return {"api_key": s.fpt_api_key, "base_url": s.fpt_base_url, "model": s.fpt_model}
    if not (s.openai_api_key or s.openai_base_url):
        raise RuntimeError("Thiếu OPENAI_API_KEY (hoặc OPENAI_BASE_URL) cho LLM_PROVIDER=openai/local.")
    return {"api_key": s.openai_api_key or "not-needed-for-local",
            "base_url": s.openai_base_url, "model": s.openai_model}
