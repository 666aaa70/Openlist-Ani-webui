"""Strict whitelisted async HTTP client for Openlist-Ani internal API.

Only the explicitly approved Openlist-Ani endpoints are callable through this client.
Administrative endpoints such as POST /api/restart are intentionally excluded, and
arbitrary URL proxying is structurally impossible.
"""

from __future__ import annotations

import time
from datetime import UTC, datetime
from pathlib import PurePosixPath
from typing import Any

import httpx

from .schemas import (
    CreateDownloadRequest,
    CreateDownloadResponse,
    DownloadPreflightRequest,
    DownloadPreflightResponse,
    DownloadTaskResponse,
    ResolveFileItem,
    ResolveResourceResponse,
    ServiceHealthResponse,
    UpstreamWorkersStatus,
)
from .security import validate_task_id
from .storage import StateStore

# Mirrors openlist_ani.application.collection.VIDEO_EXTENSIONS verbatim
VIDEO_EXTENSIONS: frozenset[str] = frozenset(
    {".mp4", ".mkv", ".avi", ".mov", ".flv", ".wmv", ".webm", ".mpg", ".mpeg"}
)

# Mirrors openlist_ani resolve_magnet.py incomplete-inspection error codes
INCOMPLETE_INSPECTION_ERROR_CODES: frozenset[str] = frozenset(
    {
        "libtorrent_unavailable",
        "metadata_fetch_failed",
        "metadata_timeout",
        "file_list_unavailable",
    }
)


class UpstreamError(Exception):
    """Base error for Openlist-Ani upstream failures."""

    def __init__(
        self,
        *,
        status_code: int,
        code: str,
        message: str,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.message = message
        self.details = details or {}


class UpstreamUnreachableError(UpstreamError):
    def __init__(self, message: str = "无法连接到 Openlist-Ani 服务，请检查服务是否已启动及地址配置") -> None:
        super().__init__(status_code=502, code="upstream_unreachable", message=message)


class UpstreamTimeoutError(UpstreamError):
    def __init__(self, message: str = "请求 Openlist-Ani 服务超时，请稍后重试或在设置中调大超时时间") -> None:
        super().__init__(status_code=504, code="upstream_timeout", message=message)


class UpstreamNotFoundError(UpstreamError):
    def __init__(self, message: str = "未找到对应的下载任务") -> None:
        super().__init__(status_code=404, code="task_not_found", message=message)


class UpstreamHttpError(UpstreamError):
    def __init__(self, upstream_status: int, detail: str) -> None:
        super().__init__(
            status_code=502,
            code="upstream_http_error",
            message=f"Openlist-Ani 返回异常状态 ({upstream_status}): {detail}",
            details={"upstream_status": upstream_status},
        )


class UpstreamInvalidResponseError(UpstreamError):
    def __init__(self, message: str = "Openlist-Ani 返回了无法解析的响应数据") -> None:
        super().__init__(status_code=502, code="upstream_invalid_response", message=message)


def _is_video_filename(name: str) -> bool:
    return PurePosixPath(name).suffix.lower() in VIDEO_EXTENSIONS


def _utc_now_iso() -> str:
    return datetime.now(UTC).isoformat()


class OpenlistAniClient:
    """Whitelisted reverse-proxy client to Openlist-Ani."""

    def __init__(
        self,
        store: StateStore,
        *,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._store = store
        self._transport = transport
        self._client: httpx.AsyncClient | None = None
        self._client_base_url: str = ""

    def _timeout_for(self, timeout_seconds: float) -> httpx.Timeout:
        return httpx.Timeout(
            connect=min(10.0, timeout_seconds),
            read=timeout_seconds,
            write=min(15.0, timeout_seconds),
            pool=min(10.0, timeout_seconds),
        )

    async def _get_client(self) -> httpx.AsyncClient:
        settings = self._store.get_settings()
        base_url = settings.upstream_url
        if self._client is not None and (
            self._client.is_closed or self._client_base_url != base_url
        ):
            old = self._client
            self._client = None
            if not old.is_closed:
                await old.aclose()

        if self._client is None:
            self._client = httpx.AsyncClient(
                base_url=base_url,
                follow_redirects=False,
                transport=self._transport,
                limits=httpx.Limits(max_connections=20, max_keepalive_connections=10),
            )
            self._client_base_url = base_url
        return self._client

    async def aclose(self) -> None:
        if self._client is not None and not self._client.is_closed:
            await self._client.aclose()
        self._client = None

    async def _request_json(
        self,
        method: str,
        path: str,
        *,
        json_body: dict[str, Any] | None = None,
        timeout_override: float | None = None,
        allow_404: bool = False,
    ) -> dict[str, Any] | None:
        settings = self._store.get_settings()
        effective_timeout = timeout_override or settings.api_timeout_seconds

        try:
            client = await self._get_client()
            response = await client.request(
                method,
                path,
                json=json_body,
                timeout=self._timeout_for(effective_timeout),
            )
        except httpx.TimeoutException as exc:
            raise UpstreamTimeoutError() from exc
        except httpx.HTTPError as exc:
            raise UpstreamUnreachableError() from exc

        if response.status_code == 404 and allow_404:
            return None

        if response.status_code >= 400:
            detail = response.text[:300]
            try:
                parsed_err = response.json()
                if isinstance(parsed_err, dict) and parsed_err.get("detail"):
                    detail = str(parsed_err["detail"])
            except Exception:
                pass
            if response.status_code == 404:
                raise UpstreamNotFoundError(detail or "未找到目标资源")
            raise UpstreamHttpError(response.status_code, detail)

        try:
            payload = response.json()
        except ValueError as exc:
            raise UpstreamInvalidResponseError() from exc

        if not isinstance(payload, dict):
            raise UpstreamInvalidResponseError()
        return payload

    # ── Whitelisted Endpoint 1 & 2: /health/live & /health/ready ─────

    async def check_health(self) -> ServiceHealthResponse:
        settings = self._store.get_settings()
        probe_timeout = self._timeout_for(min(settings.api_timeout_seconds, 10.0))
        start = time.monotonic()

        live_ok = False
        ready_ok = False
        upstream_status = "unreachable"
        degraded: dict[str, str] = {}
        workers: UpstreamWorkersStatus | None = None
        error_code: str | None = None
        error_message: str | None = None

        try:
            client = await self._get_client()
            live_resp = await client.get("/health/live", timeout=probe_timeout)
            if live_resp.status_code == 200:
                try:
                    live_data = live_resp.json()
                    live_ok = isinstance(live_data, dict) and live_data.get("status") == "live"
                except ValueError:
                    live_ok = False

            ready_resp = await client.get("/health/ready", timeout=probe_timeout)
            latency_ms = int((time.monotonic() - start) * 1000)
            try:
                ready_data: Any = ready_resp.json()
            except ValueError:
                ready_data = None

            if isinstance(ready_data, dict) and ("status" in ready_data or "ready" in ready_data):
                ready_ok = bool(ready_data.get("ready", False)) and ready_resp.status_code == 200
                upstream_status = str(
                    ready_data.get("status") or ("ready" if ready_ok else "not_ready")
                )
                raw_degraded = ready_data.get("degraded")
                if isinstance(raw_degraded, dict):
                    degraded = {str(k): str(v) for k, v in raw_degraded.items()}
                raw_workers = ready_data.get("workers")
                if isinstance(raw_workers, dict):
                    try:
                        workers = UpstreamWorkersStatus(
                            running=int(raw_workers.get("running", 0)),
                            expected=int(raw_workers.get("expected", 0)),
                        )
                    except (TypeError, ValueError):
                        workers = None
            else:
                upstream_status = "invalid_response"
                error_code = "upstream_invalid_response"
                error_message = (
                    "目标地址返回的不是 Openlist-Ani 健康检查 JSON，请确认配置的是 Openlist-Ani 后端端口（默认 26666）"
                )

            return ServiceHealthResponse(
                upstream_reachable=True,
                upstream_live=live_ok,
                upstream_ready=ready_ok,
                upstream_status=upstream_status,
                degraded=degraded,
                workers=workers,
                latency_ms=latency_ms,
                error_code=error_code,
                error_message=error_message,
                checked_at=_utc_now_iso(),
            )
        except httpx.TimeoutException:
            return ServiceHealthResponse(
                upstream_reachable=False,
                upstream_live=False,
                upstream_ready=False,
                upstream_status="timeout",
                latency_ms=int((time.monotonic() - start) * 1000),
                error_code="upstream_timeout",
                error_message="连接 Openlist-Ani 服务超时",
                checked_at=_utc_now_iso(),
            )
        except httpx.HTTPError:
            return ServiceHealthResponse(
                upstream_reachable=False,
                upstream_live=False,
                upstream_ready=False,
                upstream_status="unreachable",
                latency_ms=int((time.monotonic() - start) * 1000),
                error_code="upstream_unreachable",
                error_message="无法连接到 Openlist-Ani 服务，请检查服务是否运行以及地址是否正确",
                checked_at=_utc_now_iso(),
            )

    # ── Whitelisted Endpoint 3: POST /api/resolve_magnet ─────────────

    async def resolve_magnet(
        self,
        *,
        magnet: str,
        metadata_timeout: int = 30,
    ) -> ResolveResourceResponse:
        settings = self._store.get_settings()
        # Allow enough HTTP read time for libtorrent metadata fetch
        http_timeout = max(settings.api_timeout_seconds, float(metadata_timeout) + 15.0)
        data = await self._request_json(
            "POST",
            "/api/resolve_magnet",
            json_body={"magnet": magnet, "metadata_timeout": metadata_timeout},
            timeout_override=http_timeout,
        )
        assert data is not None
        return self._parse_resolve_response(data, resource_type="magnet")

    # ── Whitelisted Endpoint 4: POST /api/resolve_torrent ────────────

    async def resolve_torrent(self, *, url: str) -> ResolveResourceResponse:
        settings = self._store.get_settings()
        http_timeout = max(settings.api_timeout_seconds, 45.0)
        data = await self._request_json(
            "POST",
            "/api/resolve_torrent",
            json_body={"url": url},
            timeout_override=http_timeout,
        )
        assert data is not None
        return self._parse_resolve_response(data, resource_type="torrent")

    def _parse_resolve_response(
        self,
        data: dict[str, Any],
        *,
        resource_type: str,
    ) -> ResolveResourceResponse:
        raw_files = data.get("files") or []
        files: list[ResolveFileItem] = []
        video_count = 0
        if isinstance(raw_files, list):
            for entry in raw_files:
                if not isinstance(entry, dict):
                    continue
                name = str(entry.get("name") or "")
                size = int(entry.get("size") or 0)
                is_video = _is_video_filename(name)
                if is_video:
                    video_count += 1
                files.append(ResolveFileItem(name=name, size=size, is_video=is_video))

        error_code = str(data["error_code"]) if data.get("error_code") is not None else None
        inspection_incomplete = (
            resource_type == "magnet" and error_code in INCOMPLETE_INSPECTION_ERROR_CODES
        )
        collection_hint = video_count > 1 or inspection_incomplete

        return ResolveResourceResponse(
            success=bool(data.get("success", False)),
            message=str(data.get("message") or ""),
            title=str(data["title"]) if data.get("title") is not None else None,
            source=str(data["source"]) if data.get("source") is not None else None,
            error_code=error_code,
            file_count=int(data["file_count"]) if data.get("file_count") is not None else None,
            files=files,
            video_file_count=video_count,
            inspection_incomplete=inspection_incomplete,
            collection_hint=collection_hint,
            resource_type="magnet" if resource_type == "magnet" else "torrent",
        )

    # ── Whitelisted Endpoint 5: POST /api/downloads/preflight ────────

    async def preflight_download(
        self,
        payload: DownloadPreflightRequest,
    ) -> DownloadPreflightResponse:
        data = await self._request_json(
            "POST",
            "/api/downloads/preflight",
            json_body=payload.model_dump(),
        )
        assert data is not None
        try:
            return DownloadPreflightResponse.model_validate(data)
        except Exception as exc:
            raise UpstreamInvalidResponseError() from exc

    # ── Whitelisted Endpoint 6: POST /api/downloads ──────────────────

    async def create_download(
        self,
        payload: CreateDownloadRequest,
    ) -> CreateDownloadResponse:
        data = await self._request_json(
            "POST",
            "/api/downloads",
            json_body=payload.model_dump(),
        )
        assert data is not None
        try:
            return CreateDownloadResponse.model_validate(data)
        except Exception as exc:
            raise UpstreamInvalidResponseError() from exc

    # ── Whitelisted Endpoint 7: GET /api/downloads ───────────────────

    async def list_downloads(self) -> list[DownloadTaskResponse]:
        data = await self._request_json("GET", "/api/downloads")
        assert data is not None
        raw_tasks = data.get("tasks")
        if not isinstance(raw_tasks, list):
            raise UpstreamInvalidResponseError()
        try:
            return [DownloadTaskResponse.model_validate(item) for item in raw_tasks]
        except Exception as exc:
            raise UpstreamInvalidResponseError() from exc

    # ── Whitelisted Endpoint 8: GET /api/downloads/{task_id} ─────────

    async def get_download(self, task_id: str) -> DownloadTaskResponse | None:
        safe_id = validate_task_id(task_id)
        data = await self._request_json(
            "GET",
            f"/api/downloads/{safe_id}",
            allow_404=True,
        )
        if data is None:
            return None
        try:
            return DownloadTaskResponse.model_validate(data)
        except Exception as exc:
            raise UpstreamInvalidResponseError() from exc
