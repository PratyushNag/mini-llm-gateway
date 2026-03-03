from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    app_env: Literal["local", "demo", "production"] = "demo"
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    database_url: str = "sqlite+aiosqlite:///./llm_gateway.db"
    redis_url: str = "redis://localhost:6379/0"
    openrouter_base_url: str = "https://openrouter.ai/api/v1"
    openrouter_api_key: str = ""
    openrouter_http_referer: str = "http://localhost:8000"
    openrouter_app_title: str = "llm-gateway"
    enable_demo_mode: bool = True
    demo_upstream_mode: Literal["mock", "openrouter"] = "mock"
    default_route_policy: str = "balanced"
    default_cache_ttl_seconds: int = 300
    prometheus_enabled: bool = True
    log_body_capture_default: bool = False
    admin_bootstrap_token: str = "bootstrap-demo-token"
    demo_project_name: str = "demo-project"
    demo_project_api_key: str = "lgw_demo_local_key"
    routes_config_path: Path = Field(default=Path("config/routes.yml"))

    @property
    def demo_enabled(self) -> bool:
        return self.app_env == "demo" or self.enable_demo_mode


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
