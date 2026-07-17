"""Cấu hình worker — đọc từ .env (pydantic-settings). Hạ tầng bắt buộc (Docker)."""

from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class WorkerSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Hạ tầng
    rabbitmq_url: str = "amqp://guest:guest@rabbitmq:5672/"
    redis_url: str = "redis://redis:6379/0"
    database_url: str = "postgresql+asyncpg://quto:quto@postgres:5432/quto"

    # LLM (mock | openai | gemini) — dùng bởi shared/llm.py
    llm_provider: str = "mock"
    openai_api_key: str = ""
    openai_base_url: str = "https://api.openai.com/v1"
    openai_model: str = "gpt-4o-mini"
    gemini_api_key: str = ""
    gemini_model: str = "gemini-1.5-flash"

    # TTS (mock | mms) — dùng bởi shared/tts.py
    tts_provider: str = "mock"

    # Thời tiết (openmeteo | mock) — dùng bởi shared/weather.py
    weather_provider: str = "openmeteo"
    openmeteo_base_url: str = "https://api.open-meteo.com/v1/forecast"

    # Human-in-the-loop: cấp >= ngưỡng phải chờ cán bộ duyệt (1..5). 3 = cam.
    human_approval_min_level: int = 3

    # Zalo: mock | live
    zalo_provider: str = "mock"
    zalo_oa_id: str = ""
    zalo_app_id: str = ""
    zalo_secret: str = ""

    # Tuning
    prefetch: int = 8
    dispatch_max_retry: int = 3


@lru_cache
def get_worker_settings() -> WorkerSettings:
    return WorkerSettings()
