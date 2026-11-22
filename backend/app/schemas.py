"""Strict Pydantic v2 schemas matching Openlist-Ani's actual HTTP API and WebUI endpoints."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator


# ── Unified Error Schema ─────────────────────────────────────────────


class ApiErrorResponse(BaseModel):
    code: str
    message: str
    details: dict[str, Any] = Field(default_factory=dict)


# ── Authentication Schemas ───────────────────────────────────────────


class LoginRequest(BaseModel):
    username: str = Field(..., min_length=1, max_length=64)
    password: str = Field(..., min_length=1, max_length=256)


class AuthUserResponse(BaseModel):
    authenticated: bool
    username: str
    csrf_token: str


class LogoutResponse(BaseModel):
    success: bool
    message: str


# ── Health Schemas (mirrors Openlist-Ani /health/live & /health/ready) ──


class UpstreamWorkersStatus(BaseModel):
    running: int = 0
    expected: int = 0


class ServiceHealthResponse(BaseModel):
    webui_status: Literal["ok"] = "ok"
    upstream_reachable: bool
    upstream_live: bool
    upstream_ready: bool
    upstream_status: str
    degraded: dict[str, str] = Field(default_factory=dict)
    workers: UpstreamWorkersStatus | None = None
    latency_ms: int | None = None
    error_code: str | None = None
    error_message: str | None = None
    checked_at: str


# ── Openlist-Ani Resolve Schemas ─────────────────────────────────────


class ResolveMagnetRequest(BaseModel):
    magnet: str = Field(..., min_length=8, max_length=8192)
    metadata_timeout: int = Field(default=30, ge=5, le=120)

    @field_validator("magnet")
    @classmethod
    def _validate_magnet(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned.lower().startswith("magnet:?"):
            raise ValueError("请输入有效的 magnet:? 磁力链接")
        return cleaned


class ResolveTorrentRequest(BaseModel):
    url: str = Field(..., min_length=10, max_length=4096)

    @field_validator("url")
    @classmethod
    def _validate_torrent_url(cls, value: str) -> str:
        cleaned = value.strip()
        if not (cleaned.startswith("http://") or cleaned.startswith("https://")):
            raise ValueError("请输入有效的 http:// 或 https:// 种子链接")
        return cleaned


class ResolveFileItem(BaseModel):
    name: str
    size: int = 0
    is_video: bool = False


class ResolveResourceResponse(BaseModel):
    """Exact Openlist-Ani resolve response plus transparent collection analysis."""

    success: bool
    message: str
    title: str | None = None
    source: str | None = None
    error_code: str | None = None
    file_count: int | None = None
    files: list[ResolveFileItem] = Field(default_factory=list)
    video_file_count: int = 0
    inspection_incomplete: bool = False
    collection_hint: bool = False
    resource_type: Literal["magnet", "torrent"]


# ── Openlist-Ani Download Schemas (exact match to adapters/http/schemas.py) ──


class PolicyConflictResponse(BaseModel):
    key: str
    code: str
    reason: str
    matched: str = ""
    details: dict[str, Any] = Field(default_factory=dict)


class DownloadPreflightRequest(BaseModel):
    download_url: str = Field(..., min_length=8, max_length=8192)
    title: str = Field(..., min_length=1, max_length=1024)
    collection_hint: bool = False

    @field_validator("download_url")
    @classmethod
    def _validate_download_url(cls, value: str) -> str:
        cleaned = value.strip()
        lower = cleaned.lower()
        if not (
            lower.startswith("magnet:?")
            or lower.startswith("http://")
            or lower.startswith("https://")
        ):
            raise ValueError("下载链接必须是 magnet:? 或 http(s):// 地址")
        return cleaned

    @field_validator("title")
    @classmethod
    def _validate_title(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("番剧标题不能为空，无法解析时请手动输入真实标题")
        return cleaned


class DownloadPreflightResponse(BaseModel):
    success: bool
    message: str
    confirmation_required: bool = False
    policy_conflicts: list[PolicyConflictResponse] = Field(default_factory=list)
    policy_warnings: list[str] = Field(default_factory=list)
    policy_review_token: str | None = None


class CreateDownloadRequest(BaseModel):
    download_url: str = Field(..., min_length=8, max_length=8192)
    title: str = Field(..., min_length=1, max_length=1024)
    collection_hint: bool = False
    override_policy: bool = False
    acknowledged_conflicts: list[str] = Field(default_factory=list)
    policy_review_token: str | None = None

    @field_validator("download_url")
    @classmethod
    def _validate_download_url(cls, value: str) -> str:
        cleaned = value.strip()
        lower = cleaned.lower()
        if not (
            lower.startswith("magnet:?")
            or lower.startswith("http://")
            or lower.startswith("https://")
        ):
            raise ValueError("下载链接必须是 magnet:? 或 http(s):// 地址")
        return cleaned

    @field_validator("title")
    @classmethod
    def _validate_title(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("番剧标题为必填字段，不能留空或伪造")
        return cleaned


class DownloadItemResponse(BaseModel):
    item_key: str
    state: str
    source_path: str | None = None
    final_path: str | None = None
    error: str | None = None
    anime_name: str | None = None
    season: int | None = None
    episode: int | None = None


class DownloadTaskResponse(BaseModel):
    id: str
    title: str
    download_url: str
    state: str
    anime_name: str | None = None
    season: int | None = None
    episode: int | None = None
    fansub: str | None = None
    quality: str | None = None
    error_message: str | None = None
    retry_count: int = 0
    created_at: str
    updated_at: str
    started_at: str | None = None
    completed_at: str | None = None
    save_path: str = ""
    final_path: str | None = None
    final_paths: list[str] = Field(default_factory=list)
    warning_count: int = 0
    items: list[DownloadItemResponse] = Field(default_factory=list)


class DownloadListResponse(BaseModel):
    tasks: list[DownloadTaskResponse]
    total: int
    active_count: int = 0
    completed_count: int = 0
    failed_count: int = 0
    cancelled_count: int = 0
    synced_at: str


class CreateDownloadResponse(BaseModel):
    success: bool
    message: str
    task: DownloadTaskResponse | None = None
    confirmation_required: bool = False
    policy_conflicts: list[PolicyConflictResponse] = Field(default_factory=list)
    policy_warnings: list[str] = Field(default_factory=list)
    policy_review_token: str | None = None


# ── Settings Schemas ─────────────────────────────────────────────────


class SettingsResponse(BaseModel):
    upstream_configured: bool
    upstream_masked: str
    api_timeout_seconds: float
    poll_interval_seconds: int
    theme: Literal["dark", "light"]
    language: Literal["zh-CN", "en-US"]


class UpdateSettingsRequest(BaseModel):
    upstream_url: str | None = Field(
        default=None,
        description="Optional new internal Openlist-Ani base URL; omit or leave empty to keep current",
    )
    api_timeout_seconds: float | None = Field(default=None, ge=3.0, le=300.0)
    poll_interval_seconds: int | None = Field(default=None, ge=2, le=120)
    theme: Literal["dark", "light"] | None = None
    language: Literal["zh-CN", "en-US"] | None = None

    @field_validator("upstream_url")
    @classmethod
    def _empty_to_none(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = value.strip()
        return cleaned if cleaned else None
