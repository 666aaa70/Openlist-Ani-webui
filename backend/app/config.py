"""Environment configuration for Openlist-Ani WebUI backend."""

from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class AppConfig(BaseSettings):
    """Runtime settings loaded from environment variables and optional .env file."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # Upstream Openlist-Ani internal API (never exposed raw to browsers)
    openlist_ani_url: str = Field(
        default="http://127.0.0.1:26666",
        description="Internal base URL of Openlist-Ani HTTP backend",
    )
    openlist_ani_timeout: float = Field(
        default=30.0,
        ge=3.0,
        le=300.0,
        description="Default HTTP timeout (seconds) when calling Openlist-Ani",
    )
    webui_allowed_upstream_hosts: str = Field(
        default="",
        description="Optional comma-separated whitelist of allowed upstream hostnames/IPs",
    )

    # WebUI authentication
    webui_username: str = Field(
        default="admin",
        min_length=1,
        max_length=64,
        description="WebUI login username",
    )
    webui_password: str = Field(
        default="",
        description="WebUI plaintext password (prefer WEBUI_PASSWORD_HASH in production)",
    )
    webui_password_hash: str = Field(
        default="",
        description="Hashed WebUI password (scrypt$... or pbkdf2_sha256$...)",
    )

    # Session & cookie security
    webui_session_cookie_name: str = Field(default="oani_session")
    webui_session_ttl_seconds: int = Field(default=60 * 60 * 24 * 7, ge=300, le=60 * 60 * 24 * 30)
    webui_cookie_secure: Literal["auto", "true", "false"] = Field(default="auto")
    webui_trust_proxy: bool = Field(
        default=False,
        description="Trust X-Forwarded-For / X-Forwarded-Proto from reverse proxy (e.g. 1Panel OpenResty)",
    )
    webui_allowed_origins: str = Field(
        default="",
        description="Optional comma-separated extra allowed Origin values for CSRF origin verification",
    )

    # Login rate limiting
    webui_login_rate_limit_max: int = Field(default=5, ge=1, le=100)
    webui_login_rate_limit_window_seconds: int = Field(default=300, ge=10, le=3600)

    # Polling / UI defaults
    webui_default_poll_interval: int = Field(default=5, ge=2, le=120)
    webui_default_theme: Literal["dark", "light"] = Field(default="dark")
    webui_default_language: Literal["zh-CN", "en-US"] = Field(default="zh-CN")

    # Persistence & static files
    webui_data_dir: Path = Field(default=Path("./data"))
    webui_static_dir: Path | None = Field(default=None)
    webui_host: str = Field(default="0.0.0.0")
    webui_port: int = Field(default=8080, ge=1, le=65535)
    webui_log_level: str = Field(default="info")

    @field_validator("webui_username")
    @classmethod
    def _strip_username(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("WEBUI_USERNAME cannot be empty")
        return cleaned

    @property
    def db_path(self) -> Path:
        return self.webui_data_dir / "webui.db"

    @property
    def allowed_upstream_hosts_set(self) -> frozenset[str]:
        if not self.webui_allowed_upstream_hosts.strip():
            return frozenset()
        return frozenset(
            item.strip().lower()
            for item in self.webui_allowed_upstream_hosts.split(",")
            if item.strip()
        )

    @property
    def allowed_origins_set(self) -> frozenset[str]:
        if not self.webui_allowed_origins.strip():
            return frozenset()
        return frozenset(
            item.strip().rstrip("/").lower()
            for item in self.webui_allowed_origins.split(",")
            if item.strip()
        )

    def validate_auth_configured(self) -> None:
        if not self.webui_password and not self.webui_password_hash:
            raise RuntimeError(
                "WebUI 认证未配置：请设置环境变量 WEBUI_PASSWORD 或 WEBUI_PASSWORD_HASH 后再启动。"
            )
