from __future__ import annotations

from decimal import Decimal
from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "billing-agent"
    environment: Literal["development", "test", "production"] = "development"
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    max_request_body_bytes: int = 8192
    api_rate_limit_requests: int = 60
    api_rate_limit_window_seconds: int = 60

    database_url: str = "sqlite+aiosqlite:///./billing_agent.db"
    database_echo: bool = False

    llm_model: str = "billing-local"
    llm_timeout_seconds: float = 10.0
    litellm_base_url: str = "http://localhost:4000"
    litellm_api_key: str | None = None
    flightdeck_ui_base_url: str = "https://flightdeck.example.com"

    mcp_server_url: str = "http://localhost:9000/mcp"
    mcp_timeout_seconds: float = 5.0
    mcp_client_mode: Literal["local", "http"] = "local"
    mcp_service_token: str = "dev-mcp-token"
    mcp_retry_attempts: int = 3
    mcp_retry_backoff_seconds: float = 0.2
    mcp_circuit_breaker_threshold: int = 3
    mcp_circuit_breaker_cooldown_seconds: float = 30.0

    auto_credit_limit: Decimal = Decimal("25.00")
    max_credit_limit: Decimal = Decimal("500.00")
    supported_currency: str = "USD"

    max_message_length: int = 2000

    auth_mode: Literal["api_key", "oidc_introspection"] = "api_key"
    auth_introspection_url: str | None = None
    auth_introspection_timeout_seconds: float = 5.0
    auth_introspection_client_id: str | None = None
    auth_introspection_client_secret: str | None = None
    auth_role_claim: str = "roles"
    auth_scope_claim: str = "scope"
    auth_read_role: str = "billing.read"
    auth_write_role: str = "billing.write"
    auth_approve_role: str = "billing.approve"
    auth_admin_role: str = "billing.admin"

    auth_read_key: str = "dev-read-key"
    auth_write_key: str = "dev-write-key"
    auth_approve_key: str = "dev-approve-key"
    auth_admin_key: str = "dev-admin-key"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
