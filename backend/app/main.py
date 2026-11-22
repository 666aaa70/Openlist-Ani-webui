"""FastAPI application factory for Openlist-Ani WebUI."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any

import httpx
from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles

from .config import AppConfig
from .routers import auth, downloads, health, settings as settings_router
from .security import LoginRateLimiter, validate_upstream_url
from .storage import StateStore
from .upstream import OpenlistAniClient, UpstreamError

logger = logging.getLogger("openlist_ani_webui")


def _resolve_static_dir(config: AppConfig) -> Path | None:
    if config.webui_static_dir is not None:
        candidate = config.webui_static_dir
        return candidate if (candidate / "index.html").is_file() else None
    default_dist = Path(__file__).resolve().parents[2] / "frontend" / "dist"
    if (default_dist / "index.html").is_file():
        return default_dist
    return None


def create_app(
    config: AppConfig | None = None,
    *,
    upstream_transport: httpx.AsyncBaseTransport | None = None,
) -> FastAPI:
    cfg = config or AppConfig()
    cfg.validate_auth_configured()
    # Validate configured default upstream URL early on startup
    validate_upstream_url(
        cfg.openlist_ani_url,
        allowed_hosts=cfg.allowed_upstream_hosts_set,
    )

    store = StateStore(cfg)
    upstream = OpenlistAniClient(store, transport=upstream_transport)
    rate_limiter = LoginRateLimiter(
        max_attempts=cfg.webui_login_rate_limit_max,
        window_seconds=cfg.webui_login_rate_limit_window_seconds,
    )

    @asynccontextmanager
    async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
        logger.info("Openlist-Ani WebUI backend initialized")
        yield
        logger.info("Openlist-Ani WebUI backend shutting down")

    app = FastAPI(
        title="Openlist-Ani WebUI Backend",
        version="0.1.0",
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
        lifespan=lifespan,
    )

    app.state.config = cfg
    app.state.store = store
    app.state.upstream = upstream
    app.state.rate_limiter = rate_limiter

    @app.middleware("http")
    async def security_headers_middleware(request: Request, call_next) -> Response:
        response = await call_next(request)
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Referrer-Policy", "same-origin")
        response.headers.setdefault(
            "Permissions-Policy", "camera=(), microphone=(), geolocation=()"
        )
        if request.url.path.startswith("/api/"):
            response.headers["Cache-Control"] = "no-store"
        return response

    @app.exception_handler(UpstreamError)
    async def upstream_error_handler(_request: Request, exc: UpstreamError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "code": exc.code,
                "message": exc.message,
                "details": exc.details,
            },
        )

    @app.exception_handler(HTTPException)
    async def http_exception_handler(_request: Request, exc: HTTPException) -> JSONResponse:
        if isinstance(exc.detail, dict):
            body: dict[str, Any] = {
                "code": str(exc.detail.get("code", "http_error")),
                "message": str(exc.detail.get("message", "请求失败")),
                "details": exc.detail.get("details", {}),
            }
        else:
            body = {
                "code": "http_error",
                "message": str(exc.detail),
                "details": {},
            }
        return JSONResponse(
            status_code=exc.status_code,
            content=body,
            headers=exc.headers,
        )

    @app.exception_handler(RequestValidationError)
    async def validation_error_handler(
        _request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        errors = exc.errors()
        first_msg = "请求参数校验失败"
        if errors:
            raw_msg = str(errors[0].get("msg", first_msg))
            if raw_msg.startswith("Value error, "):
                raw_msg = raw_msg[len("Value error, ") :]
            first_msg = raw_msg
        return JSONResponse(
            status_code=422,
            content={
                "code": "validation_error",
                "message": first_msg,
                "details": {"errors": [{"loc": e.get("loc"), "msg": e.get("msg")} for e in errors]},
            },
        )

    app.include_router(auth.router)
    app.include_router(health.router)
    app.include_router(downloads.router)
    app.include_router(settings_router.router)

    @app.api_route(
        "/api/{rest:path}",
        methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        include_in_schema=False,
    )
    async def api_not_found(rest: str) -> JSONResponse:
        del rest
        return JSONResponse(
            status_code=404,
            content={"code": "not_found", "message": "接口不存在", "details": {}},
        )

    # Serve built Vue SPA if available (single-container production deployment)
    static_dir = _resolve_static_dir(cfg)
    if static_dir is not None:
        assets_dir = static_dir / "assets"
        if assets_dir.is_dir():
            app.mount("/assets", StaticFiles(directory=assets_dir), name="assets")

        index_file = static_dir / "index.html"
        static_root = static_dir.resolve()

        @app.get("/{full_path:path}", include_in_schema=False)
        async def serve_spa(full_path: str) -> Response:
            if full_path:
                candidate = (static_root / full_path).resolve()
                if (
                    candidate.is_file()
                    and static_root in candidate.parents
                ):
                    return FileResponse(candidate)
            return FileResponse(index_file)

    return app


def get_asgi_app() -> FastAPI:
    return create_app()
