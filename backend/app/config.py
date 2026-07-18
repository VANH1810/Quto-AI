from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Cấu hình đọc từ biến môi trường / .env. Mặc định chạy full mock."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "Ban Tin An Toan - Dien Bien EWS"
    app_version: str = "0.1.0"

    # Nguồn thời tiết: openmeteo | mock
    weather_provider: str = "openmeteo"
    openmeteo_base_url: str = "https://api.open-meteo.com/v1/forecast"
    weather_timeout_seconds: float = 12.0
    weather_cache_ttl_seconds: int = 600
    commune_overview_cache_ttl_seconds: int = 300

    # LLM: mock | openai | gemini | local
    llm_provider: str = "mock"
    openai_api_key: str = ""
    openai_base_url: str = "https://api.openai.com/v1"
    openai_model: str = "gpt-4o-mini"
    gemini_api_key: str = ""
    gemini_model: str = "gemini-1.5-flash"

    # TTS: mock | mms
    tts_provider: str = "mock"

    # Dispatch: mock | live
    dispatch_provider: str = "mock"

    # Nơi lưu dữ liệu: memory (in-memory, chạy ngay) | supabase (Postgres)
    db_backend: str = "memory"
    supabase_url: str = ""
    supabase_key: str = ""  # dùng service_role key ở backend (KHÔNG lộ ra client)

    # Cấp độ tối thiểu cần người duyệt trước khi gửi (1..5). 3 = cam.
    human_approval_min_level: int = 3

    # JWT
    jwt_secret: str = "dev-secret-doi-truoc-khi-len-that"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 240

    # Frontend public map và admin console chạy khác port khi phát triển local.
    # Chuỗi CSV giúp cấu hình .env đơn giản, không cần JSON list của Pydantic.
    cors_origins: str = "http://localhost:3000,http://localhost:3001"

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
