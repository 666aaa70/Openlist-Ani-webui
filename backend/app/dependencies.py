"""FastAPI dependencies for authentication, CSRF protection, and runtime components."""

from __future__ import annotations

from fastapi import Depends, HTTPException, Request, status

from .config import AppConfig
from .security import (
    LoginRateLimiter,
    extract_client_ip,
    validate_request_origin,
    verify_csrf_token,
)
from .storage import SessionRecord, StateStore
from .upstream import OpenlistAniClient


def get_config(request: Request) -> AppConfig:
    return request.app.state.config


def get_store(request: Request) -> StateStore:
    return request.app.state.store


def get_upstream(request: Request) -> OpenlistAniClient:
    return request.app.state.upstream


def get_rate_limiter(request: Request) -> LoginRateLimiter:
    return request.app.state.rate_limiter


def get_client_ip(
    request: Request,
    config: AppConfig = Depends(get_config),
) -> str:
    return extract_client_ip(request, trust_proxy=config.webui_trust_proxy)


def require_session(
    request: Request,
    config: AppConfig = Depends(get_config),
    store: StateStore = Depends(get_store),
) -> SessionRecord:
    raw_token = request.cookies.get(config.webui_session_cookie_name)
    if not raw_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "unauthenticated", "message": "请先登录"},
        )
    session = store.get_session(raw_token)
    if session is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "session_expired", "message": "登录会话已过期，请重新登录"},
        )
    return session


def require_csrf(
    request: Request,
    session: SessionRecord = Depends(require_session),
    config: AppConfig = Depends(get_config),
) -> SessionRecord:
    if not validate_request_origin(request, config):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"code": "invalid_origin", "message": "请求来源校验失败"},
        )
    provided = request.headers.get("x-csrf-token")
    if not verify_csrf_token(provided, session.csrf_token):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"code": "invalid_csrf", "message": "CSRF 令牌无效或已失效，请刷新页面重试"},
        )
    return session
